"""SnapTask authenticated HTTP API and web app, deployed as AWS Lambda."""
import base64
import hashlib
import json
import mimetypes
import os
import secrets
import time
import urllib.parse
import urllib.request
import uuid
from decimal import Decimal
from pathlib import Path

import boto3
import jwt
from botocore.exceptions import ClientError
from botocore.config import Config
from boto3.dynamodb.conditions import Key

MAX_FILE_SIZE = 25 * 1024 * 1024
_jwks = None


def table():
    return boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])


def s3():
    region = os.environ.get('AWS_REGION', os.environ.get('AWS_DEFAULT_REGION', 'eu-west-1'))
    return boto3.client('s3', region_name=region, endpoint_url='https://s3.' + region + '.amazonaws.com', config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}))


def now():
    return int(time.time())


def json_default(value):
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError('Not JSON serializable')


def response(status, data, headers=None, cookies=None):
    result = {'statusCode': status, 'headers': {'content-type': 'application/json', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff', **(headers or {})}, 'body': json.dumps(data, default=json_default)}
    if cookies:
        result['cookies'] = cookies
    return result


def read_cookie(event, name):
    cookie = '; '.join(event.get('cookies', [])) or event.get('headers', {}).get('cookie', '')
    for item in cookie.split(';'):
        k, _, v = item.strip().partition('=')
        if k == name:
            return v
    return None


def verify_jwt(token):
    global _jwks
    issuer = os.environ['AUTH_ISSUER']
    if _jwks is None:
        _jwks = jwt.PyJWKClient(issuer + '/.well-known/jwks.json')
    key = _jwks.get_signing_key_from_jwt(token)
    claims = jwt.decode(token, key.key, algorithms=['RS256'], audience=os.environ['AUTH_CLIENT_ID'], issuer=issuer, options={'require': ['exp', 'iat', 'iss', 'aud', 'sub']})
    if claims.get('token_use') != 'id':
        raise ValueError('ID token required')
    return claims


def authenticate(event):
    headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
    auth = headers.get('authorization', '')
    if auth.startswith('Bearer st_'):
        hashed = hashlib.sha256(auth[7:].encode()).hexdigest()
        lookup = table().get_item(Key={'PK': 'TOKEN#' + hashed, 'SK': 'META'}, ConsistentRead=True).get('Item')
        if not lookup:
            raise PermissionError('Invalid API token')
        return lookup['owner'], {'sub': lookup['owner'], 'name': lookup['name'], 'auth': 'api_token'}
    token = auth[7:] if auth.startswith('Bearer ') else read_cookie(event, 'snaptask_session')
    if not token:
        raise PermissionError('Sign in required')
    try:
        claims = verify_jwt(token)
    except Exception as exc:
        raise PermissionError('Session expired or invalid') from exc
    method = event.get('requestContext', {}).get('http', {}).get('method', event.get('httpMethod', 'GET'))
    if not auth and method not in ('GET', 'HEAD', 'OPTIONS'):
        if headers.get('origin', '').rstrip('/') != os.environ['APP_URL'].rstrip('/'):
            raise PermissionError('Same-origin request required')
    return claims['sub'], claims


def items(owner, prefix):
    result = []
    args = {'KeyConditionExpression': Key('PK').eq('USER#' + owner) & Key('SK').begins_with(prefix)}
    while True:
        page = table().query(**args)
        result.extend(page['Items'])
        if 'LastEvaluatedKey' not in page:
            return result
        args['ExclusiveStartKey'] = page['LastEvaluatedKey']


def public(item):
    return {k: v for k, v in item.items() if k not in ('PK', 'SK', 'owner', 'token_hash', 'secret', 'completed_uploads', 'reserved_uploads')}


def task(owner, ident):
    item = table().get_item(Key={'PK': 'USER#' + owner, 'SK': 'TASK#' + ident}, ConsistentRead=True).get('Item')
    if not item:
        raise LookupError('Task not found')
    return item


def body(event):
    raw = event.get('body') or '{}'
    if event.get('isBase64Encoded'):
        raw = base64.b64decode(raw)
    if len(raw) > 128 * 1024:
        raise ValueError('Request too large')
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError('JSON object required')
    return result


def bounded(value, name, limit=10000):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(name + ' must be text with at most ' + str(limit) + ' characters')
    return value


def auth_route(path, event):
    base = os.environ['AUTH_BASE_URL'].rstrip('/')
    redirect = os.environ['APP_URL'].rstrip('/') + '/auth/callback'
    if path == '/auth/login':
        state, verifier, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        cookie = base64.urlsafe_b64encode(json.dumps({'state': state, 'verifier': verifier, 'nonce': nonce}).encode()).decode()
        query = urllib.parse.urlencode({'client_id': os.environ['AUTH_CLIENT_ID'], 'response_type': 'code', 'scope': 'openid email profile', 'redirect_uri': redirect, 'state': state, 'nonce': nonce, 'code_challenge': challenge, 'code_challenge_method': 'S256'})
        return response(302, {}, {'location': base + '/oauth2/authorize?' + query}, ['snaptask_oauth=' + cookie + '; Max-Age=600; Path=/auth; Secure; HttpOnly; SameSite=Lax'])
    if path == '/auth/logout':
        return response(302, {}, {'location': '/'}, ['snaptask_session=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Lax'])
    query = event.get('queryStringParameters') or {}
    try:
        stored = json.loads(base64.urlsafe_b64decode(read_cookie(event, 'snaptask_oauth') or ''))
        if not secrets.compare_digest(query.get('state', ''), stored['state']):
            raise ValueError()
        payload = urllib.parse.urlencode({'grant_type': 'authorization_code', 'client_id': os.environ['AUTH_CLIENT_ID'], 'code': query['code'], 'redirect_uri': redirect, 'code_verifier': stored['verifier']}).encode()
        req = urllib.request.Request(base + '/oauth2/token', data=payload, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(req, timeout=10) as result:
            tokens = json.load(result)
        claims = verify_jwt(tokens['id_token'])
        if not secrets.compare_digest(claims.get('nonce', ''), stored['nonce']):
            raise ValueError('Invalid nonce')
    except Exception:
        return response(400, {'error': 'Sign-in failed. Please try again.'})
    return response(302, {}, {'location': '/'}, ['snaptask_oauth=; Max-Age=0; Path=/auth; Secure; HttpOnly; SameSite=Lax', 'snaptask_session=' + tokens['id_token'] + '; Max-Age=3600; Path=/; Secure; HttpOnly; SameSite=Lax'])


def handler(event, context):
    try:
        return route(event)
    except PermissionError as exc:
        return response(401, {'error': str(exc)})
    except LookupError as exc:
        return response(404, {'error': str(exc)})
    except (ValueError, TypeError, KeyError) as exc:
        return response(400, {'error': str(exc)})
    except ClientError as exc:
        if exc.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return response(409, {'error': 'Task changed; refresh and retry'})
        print(json.dumps({'error': exc.response['Error']['Code']}))
        return response(500, {'error': 'Storage operation failed'})
    except Exception as exc:
        print(json.dumps({'error_type': type(exc).__name__}))
        return response(500, {'error': 'Internal error'})


def route(event):
    path = event.get('rawPath', event.get('path', '/'))
    method = event.get('requestContext', {}).get('http', {}).get('method', event.get('httpMethod', 'GET'))
    if path in ('/auth/login', '/auth/callback', '/auth/logout'):
        return auth_route(path, event)
    if path in ('/api/config', '/health'):
        return response(200, {'name': 'SnapTask', 'login_url': '/auth/login', 'max_file_size': MAX_FILE_SIZE, 'status': 'ok'})
    if not path.startswith('/api/'):
        root = Path(__file__).resolve().parent.parent / 'web'
        name = 'index.html' if path == '/' else path.lstrip('/')
        target = (root / name).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            return response(404, {'error': 'Not found'})
        mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        return {'statusCode': 200, 'headers': {'content-type': mime, 'cache-control': 'no-cache', 'x-content-type-options': 'nosniff', 'referrer-policy': 'same-origin', 'content-security-policy': "default-src 'self'; img-src 'self' blob: data: https:; connect-src 'self' https://*.amazonaws.com; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'"}, 'body': base64.b64encode(target.read_bytes()).decode(), 'isBase64Encoded': True}
    owner, claims = authenticate(event)
    data = body(event) if method in ('POST', 'PATCH') else {}
    parts = path.strip('/').split('/')
    if path == '/api/me' and method == 'GET':
        return response(200, {'id': owner, 'email': claims.get('email'), 'name': claims.get('name', claims.get('email', 'Agent'))})
    if path in ('/api/tasks', '/api/ingest'):
        if method == 'GET' and path == '/api/tasks':
            return response(200, {'tasks': sorted([public(i) for i in items(owner, 'TASK#')], key=lambda x: x['created_at'], reverse=True)})
        if method == 'POST':
            idem = event.get('headers', {}).get('idempotency-key', event.get('headers', {}).get('Idempotency-Key'))
            ident = str(uuid.uuid5(uuid.NAMESPACE_URL, owner + ':' + bounded(idem, 'Idempotency-Key', 200))) if idem else str(uuid.uuid4())
            existing = table().get_item(Key={'PK': 'USER#' + owner, 'SK': 'TASK#' + ident}).get('Item')
            if existing:
                return response(200, public(existing))
            initial_status = data.get('status', 'todo')
            if initial_status not in ('todo', 'uploading'):
                raise ValueError('Initial status must be todo or uploading')
            title = bounded(data.get('title', 'New capture'), 'title', 300).strip() or 'New capture'
            item = {'PK': 'USER#' + owner, 'SK': 'TASK#' + ident, 'owner': owner, 'id': ident, 'title': title, 'notes': bounded(data.get('notes', ''), 'notes'), 'status': initial_status, 'created_at': now(), 'updated_at': now(), 'files': []}
            try:
                table().put_item(Item=item, ConditionExpression='attribute_not_exists(PK)')
            except ClientError as exc:
                if exc.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    raise
                return response(200, public(task(owner, ident)))
            return response(201, public(item))
    if path == '/api/tasks/claim' and method == 'POST':
        agent = bounded(data.get('agent', 'agent'), 'agent', 100)
        for item in sorted(items(owner, 'TASK#'), key=lambda x: x['created_at']):
            try:
                updated = table().update_item(Key={'PK': item['PK'], 'SK': item['SK']}, UpdateExpression='SET #s=:claimed, claimed_by=:agent, claim_token=:token, lease_until=:lease, updated_at=:now', ConditionExpression='#s=:todo OR (#s=:claimed AND lease_until < :now)', ExpressionAttributeNames={'#s': 'status'}, ExpressionAttributeValues={':claimed': 'claimed', ':todo': 'todo', ':agent': agent, ':token': secrets.token_urlsafe(24), ':lease': now() + 900, ':now': now()}, ReturnValues='ALL_NEW')['Attributes']
                return response(200, {'task': public(updated)})
            except ClientError as exc:
                if exc.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    raise
        return response(200, {'task': None})
    if len(parts) >= 3 and parts[1] == 'tasks':
        item = task(owner, parts[2])
        if len(parts) == 4 and parts[3] == 'heartbeat' and method == 'POST':
            updated = table().update_item(Key={'PK': item['PK'], 'SK': item['SK']}, UpdateExpression='SET lease_until=:lease, updated_at=:now', ConditionExpression='#s=:claimed AND claimed_by=:agent AND claim_token=:token AND lease_until>=:now', ExpressionAttributeNames={'#s': 'status'}, ExpressionAttributeValues={':lease': now() + 900, ':now': now(), ':claimed': 'claimed', ':agent': data.get('agent', ''), ':token': data.get('claim_token', '')}, ReturnValues='ALL_NEW')['Attributes']
            return response(200, public(updated))
        if len(parts) == 3:
            if method == 'GET':
                return response(200, public(item))
            if method == 'DELETE':
                # Remove the task first so no agent can discover it while attachments are deleted.
                table().delete_item(Key={'PK': item['PK'], 'SK': item['SK']})
                prefix = owner + '/' + item['id'] + '/'
                for page in s3().get_paginator('list_objects_v2').paginate(Bucket=os.environ['BUCKET_NAME'], Prefix=prefix):
                    objects = [{'Key': entry['Key']} for entry in page.get('Contents', [])]
                    if objects:
                        s3().delete_objects(Bucket=os.environ['BUCKET_NAME'], Delete={'Objects': objects})
                return response(200, {'deleted': True})
            if method == 'PATCH':
                if data.get('publish') is True and data.get('status') == 'todo' and item['status'] != 'uploading':
                    return response(200, public(item))
                updates = {}
                for key in ('title', 'notes', 'result'):
                    if key in data:
                        updates[key] = bounded(data[key], key, 300 if key == 'title' else 10000)
                if 'status' in data:
                    if data['status'] not in ('todo', 'claimed', 'done', 'uploading'):
                        raise ValueError('Invalid status')
                    if data['status'] == 'todo' and item.get('reserved_uploads', set()) - item.get('completed_uploads', set()):
                        raise ValueError('Complete every reserved upload before marking ready')
                    if item['status'] == 'claimed' and claims.get('auth') == 'api_token':
                        if data.get('claim_token') != item.get('claim_token') or item.get('lease_until', 0) < now():
                            raise PermissionError('Live claim_token required to change a claimed task')
                    updates['status'] = data['status']
                    if data['status'] == 'claimed':
                        updates['lease_until'] = now() + 900
                        updates['claimed_by'] = bounded(data.get('claimed_by', 'manual'), 'claimed_by', 100)
                updates['updated_at'] = now()
                names = {'#k' + str(i): k for i, k in enumerate(updates)}
                values = {':v' + str(i): v for i, v in enumerate(updates.values())}
                conditions = {'ConditionExpression': 'attribute_exists(PK)'}
                if 'status' in data:
                    conditions['ConditionExpression'] += ' AND #currentstatus=:expectedstatus'
                    names['#currentstatus'] = 'status'
                    values[':expectedstatus'] = item['status']
                if data.get('status') == 'todo':
                    conditions['ConditionExpression'] += ' AND (attribute_not_exists(reserved_uploads) OR reserved_uploads = completed_uploads)'
                    if data.get('publish') is True:
                        conditions['ConditionExpression'] += ' AND #publishstatus=:uploading'
                        names['#publishstatus'] = 'status'
                        values[':uploading'] = 'uploading'
                if item['status'] == 'claimed' and claims.get('auth') == 'api_token' and 'status' in data:
                    conditions['ConditionExpression'] += ' AND claim_token=:guardtoken AND lease_until>=:guardnow'
                    values.update({':guardtoken': data.get('claim_token', ''), ':guardnow': now()})
                updated = table().update_item(**conditions, Key={'PK': item['PK'], 'SK': item['SK']}, UpdateExpression='SET ' + ', '.join('#k' + str(i) + '=:v' + str(i) for i in range(len(updates))), ExpressionAttributeNames=names, ExpressionAttributeValues=values, ReturnValues='ALL_NEW')['Attributes']
                return response(200, public(updated))
        if len(parts) == 4 and parts[3] == 'uploads' and method == 'POST':
            size = data.get('size')
            if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_FILE_SIZE:
                raise ValueError('File size must be between 1 byte and 25 MB')
            idem = event.get('headers', {}).get('idempotency-key', event.get('headers', {}).get('Idempotency-Key'))
            fid = str(uuid.uuid5(uuid.NAMESPACE_URL, owner + ':' + item['id'] + ':' + bounded(idem, 'Idempotency-Key', 200))) if idem else str(uuid.uuid4())
            content_type = bounded(data.get('content_type', 'application/octet-stream'), 'content_type', 100)
            upload = {'id': fid, 'name': bounded(data.get('name', 'capture.jpg'), 'name', 250), 'size': size, 'content_type': content_type}
            key = owner + '/' + item['id'] + '/' + fid
            existing_upload = table().get_item(Key={'PK': 'USER#' + owner, 'SK': 'UPLOAD#' + fid}).get('Item')
            if fid in item.get('completed_uploads', set()):
                return response(200, {'file_id': fid, 'upload_url': None, 'completed': True})
            if item['status'] != 'uploading':
                raise ValueError('Only uploading tasks accept new files; create a staged task')
            if len(item.get('reserved_uploads', set())) >= 50 and fid not in item.get('reserved_uploads', set()):
                raise ValueError('A task can contain at most 50 files')
            if existing_upload and any(existing_upload[k] != upload[k] for k in ('name', 'size', 'content_type')):
                raise ValueError('Idempotency key already used for another file')
            if fid not in item.get('completed_uploads', set()):
                table().update_item(Key={'PK': item['PK'], 'SK': item['SK']}, UpdateExpression='ADD reserved_uploads :ids', ConditionExpression='#s=:uploading AND (attribute_not_exists(reserved_uploads) OR size(reserved_uploads)<:limit OR contains(reserved_uploads,:fid))', ExpressionAttributeNames={'#s': 'status'}, ExpressionAttributeValues={':ids': {fid}, ':uploading': 'uploading', ':limit': 50, ':fid': fid})
            table().put_item(Item={'PK': 'USER#' + owner, 'SK': 'UPLOAD#' + fid, 'task_id': item['id'], **upload, 'expires_at': now() + 86400})
            url = s3().generate_presigned_url('put_object', Params={'Bucket': os.environ['BUCKET_NAME'], 'Key': key, 'ContentType': content_type, 'ContentLength': size}, ExpiresIn=900)
            return response(201, {'file_id': fid, 'upload_url': url})
        if len(parts) == 6 and parts[3] == 'uploads' and parts[5] == 'complete' and method == 'POST':
            fid = parts[4]
            if fid in item.get('completed_uploads', set()):
                return response(200, public(item))
            upload = table().get_item(Key={'PK': 'USER#' + owner, 'SK': 'UPLOAD#' + fid}).get('Item')
            if not upload or upload['task_id'] != item['id'] or upload['expires_at'] < now():
                raise LookupError('Upload not found or expired')
            metadata = s3().head_object(Bucket=os.environ['BUCKET_NAME'], Key=owner + '/' + item['id'] + '/' + fid)
            if metadata['ContentLength'] != upload['size'] or metadata.get('ContentType') != upload['content_type']:
                raise ValueError('Uploaded file does not match declared metadata')
            attachment = {k: upload[k] for k in ('id', 'name', 'size', 'content_type')}
            try:
                updated = table().update_item(Key={'PK': item['PK'], 'SK': item['SK']}, UpdateExpression='SET files=list_append(files,:file), updated_at=:now ADD completed_uploads :id', ConditionExpression='attribute_exists(PK) AND #s=:uploading AND (attribute_not_exists(completed_uploads) OR NOT contains(completed_uploads,:fid))', ExpressionAttributeNames={'#s': 'status'}, ExpressionAttributeValues={':file': [attachment], ':now': now(), ':id': {fid}, ':fid': fid, ':uploading': 'uploading'}, ReturnValues='ALL_NEW')['Attributes']
            except ClientError as exc:
                if exc.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    raise
                updated = task(owner, item['id'])
            return response(200, public(updated))
        if len(parts) == 5 and parts[3] == 'files' and method == 'GET':
            attachment = next((f for f in item['files'] if f['id'] == parts[4]), None)
            if not attachment:
                raise LookupError('File not found')
            url = s3().generate_presigned_url('get_object', Params={'Bucket': os.environ['BUCKET_NAME'], 'Key': owner + '/' + item['id'] + '/' + parts[4], 'ResponseContentDisposition': "attachment; filename*=UTF-8''" + urllib.parse.quote(attachment['name'], safe='')}, ExpiresIn=300)
            return response(200, {'download_url': url})
    if len(parts) >= 2 and parts[1] in ('tokens', 'webhooks'):
        kind = parts[1]
        prefix = 'TOKEN#' if kind == 'tokens' else 'WEBHOOK#'
        if len(parts) == 2 and method == 'GET':
            return response(200, {kind: [public(i) for i in items(owner, prefix)]})
        if len(parts) == 2 and method == 'POST':
            ident = str(uuid.uuid4())
            item = {'PK': 'USER#' + owner, 'SK': prefix + ident, 'id': ident, 'created_at': now()}
            if kind == 'tokens':
                item['name'] = bounded(data.get('name', 'Agent'), 'name', 100)
                raw = 'st_' + secrets.token_urlsafe(32)
                item['token_hash'] = hashlib.sha256(raw.encode()).hexdigest()
                table().put_item(Item={'PK': 'TOKEN#' + item['token_hash'], 'SK': 'META', 'owner': owner, 'name': item['name']})
                table().put_item(Item=item)
                return response(201, {**public(item), 'token': raw})
            from backend.webhooks import validate_url
            item['url'] = bounded(data.get('url', ''), 'url', 2000)
            validate_url(item['url'])
            item['secret'] = secrets.token_urlsafe(32)
            table().put_item(Item=item)
            return response(201, {**public(item), 'secret': item['secret']})
        if len(parts) == 3 and method == 'DELETE':
            key = {'PK': 'USER#' + owner, 'SK': prefix + parts[2]}
            item = table().get_item(Key=key).get('Item')
            if not item:
                raise LookupError('Not found')
            if kind == 'tokens':
                table().delete_item(Key={'PK': 'TOKEN#' + item['token_hash'], 'SK': 'META'})
            table().delete_item(Key=key)
            return response(200, {'deleted': True})
    return response(404, {'error': 'Route not found'})
