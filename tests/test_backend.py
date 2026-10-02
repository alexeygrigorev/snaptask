import hashlib
import json
import os
import socket
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws
from backend import app, webhooks


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    monkeypatch.setenv('TABLE_NAME', 'test')
    monkeypatch.setenv('BUCKET_NAME', 'test-files')
    monkeypatch.setenv('APP_URL', 'https://snaptask.dtcdev.click')
    monkeypatch.setenv('AUTH_BASE_URL', 'https://auth.example.com')
    monkeypatch.setenv('AUTH_CLIENT_ID', 'client')
    with mock_aws():
        boto3.client('dynamodb').create_table(TableName='test', KeySchema=[{'AttributeName': 'PK', 'KeyType': 'HASH'}, {'AttributeName': 'SK', 'KeyType': 'RANGE'}], AttributeDefinitions=[{'AttributeName': 'PK', 'AttributeType': 'S'}, {'AttributeName': 'SK', 'AttributeType': 'S'}], BillingMode='PAY_PER_REQUEST')
        boto3.client('s3').create_bucket(Bucket='test-files')
        for owner in ('alice', 'bob'):
            raw = 'st_' + owner
            app.table().put_item(Item={'PK': 'TOKEN#' + hashlib.sha256(raw.encode()).hexdigest(), 'SK': 'META', 'owner': owner, 'name': 'test'})
        def call(method, path, data=None, owner='alice', headers=None):
            event = {'rawPath': path, 'requestContext': {'http': {'method': method}}, 'headers': {'authorization': 'Bearer st_' + owner, **(headers or {})}, 'body': json.dumps(data) if data is not None else None}
            result = app.handler(event, None)
            return result['statusCode'], json.loads(result['body'])
        yield call


def test_task_isolation_claim_and_lease(api):
    status, task = api('POST', '/api/tasks', {'title': 'Receipt'})
    assert status == 201
    assert api('GET', '/api/tasks', owner='bob')[1]['tasks'] == []
    assert api('GET', '/api/tasks/' + task['id'], owner='bob')[0] == 404
    claimed = api('POST', '/api/tasks/claim', {'agent': 'worker'})[1]['task']
    assert claimed['id'] == task['id'] and claimed['lease_until'] > app.now()
    assert api('POST', '/api/tasks/claim', {'agent': 'another'})[1]['task'] is None
    assert api('POST', '/api/tasks/' + task['id'] + '/heartbeat', {'agent': 'worker', 'claim_token': 'wrong'})[0] == 409
    assert api('POST', '/api/tasks/' + task['id'] + '/heartbeat', {'agent': 'worker', 'claim_token': claimed['claim_token']})[0] == 200
    assert api('PATCH', '/api/tasks/' + task['id'], {'status': 'done'})[0] == 401
    assert api('PATCH', '/api/tasks/' + task['id'], {'status': 'done', 'claim_token': claimed['claim_token'], 'result': 'Extracted'})[1]['status'] == 'done'


def test_upload_staging_idempotency_and_completion(api):
    payload = {'title': 'Photos', 'status': 'uploading'}
    task = api('POST', '/api/tasks', payload, headers={'idempotency-key': 'draft1'})[1]
    assert api('POST', '/api/tasks', payload, headers={'idempotency-key': 'draft1'})[1]['id'] == task['id']
    assert api('POST', '/api/tasks/claim', {'agent': 'worker'})[1]['task'] is None
    base = '/api/tasks/' + task['id']
    upload = api('POST', base + '/uploads', {'name': 'a.jpg', 'content_type': 'image/jpeg', 'size': 3}, headers={'idempotency-key': 'file1'})[1]
    repeated = api('POST', base + '/uploads', {'name': 'a.jpg', 'content_type': 'image/jpeg', 'size': 3}, headers={'idempotency-key': 'file1'})[1]
    assert upload['file_id'] == repeated['file_id']
    assert api('PATCH', base, {'status': 'todo'})[0] == 400
    boto3.client('s3').put_object(Bucket='test-files', Key='alice/' + task['id'] + '/' + upload['file_id'], Body=b'abc', ContentType='image/jpeg')
    completed = api('POST', base + '/uploads/' + upload['file_id'] + '/complete')[1]
    assert len(completed['files']) == 1
    assert len(api('POST', base + '/uploads/' + upload['file_id'] + '/complete')[1]['files']) == 1
    assert api('POST', base + '/uploads', {'name': 'a.jpg', 'content_type': 'image/jpeg', 'size': 3}, headers={'idempotency-key': 'file1'})[1]['completed'] is True
    assert api('PATCH', base, {'status': 'todo'})[0] == 200
    assert api('GET', base + '/files/' + upload['file_id'])[1]['download_url'].startswith('https://')


def test_tokens_revocation_and_hash_at_rest(api):
    token = api('POST', '/api/tokens', {'name': 'CLI'})[1]
    assert token['token'].startswith('st_')
    stored = app.table().get_item(Key={'PK': 'USER#alice', 'SK': 'TOKEN#' + token['id']})['Item']
    assert token['token'] not in str(stored)
    assert 'token' not in api('GET', '/api/tokens')[1]['tokens'][0]
    assert api('DELETE', '/api/tokens/' + token['id'])[0] == 200
    event = {'rawPath': '/api/me', 'headers': {'authorization': 'Bearer ' + token['token']}, 'requestContext': {'http': {'method': 'GET'}}}
    assert app.handler(event, None)['statusCode'] == 401


def test_browser_csrf_and_public_health(api):
    with patch.object(app, 'verify_jwt', return_value={'sub': 'alice'}):
        event = {'rawPath': '/api/tasks', 'cookies': ['snaptask_session=jwt'], 'headers': {}, 'requestContext': {'http': {'method': 'POST'}}, 'body': '{}'}
        assert app.handler(event, None)['statusCode'] == 401
        event['headers']['origin'] = os.environ['APP_URL']
        assert app.handler(event, None)['statusCode'] == 201
    assert app.handler({'rawPath': '/health'}, None)['statusCode'] == 200
    assert app.handler({'rawPath': '/../backend/app.py'}, None)['statusCode'] == 404


@pytest.mark.parametrize('url', ['http://example.com', 'https://127.0.0.1', 'https://169.254.169.254', 'https://[::1]', 'https://example.com:8443', 'https://user@example.com'])
def test_webhook_ssrf_validation(url):
    with patch.object(socket, 'getaddrinfo', return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]):
        with pytest.raises(ValueError):
            webhooks.validate_url(url)


def test_webhook_stream_signed_retry_and_stage(api):
    from boto3.dynamodb.types import TypeSerializer
    serializer = TypeSerializer()
    task = api('POST', '/api/tasks', {'title': 'Picture', 'status': 'uploading'})[1]
    app.table().put_item(Item={'PK': 'USER#alice', 'SK': 'WEBHOOK#hook', 'id': 'hook', 'url': 'https://example.com', 'secret': 'secret'})
    item = app.task('alice', task['id'])
    record = {'eventID': 'event1', 'dynamodb': {'SequenceNumber': '1', 'NewImage': {k: serializer.serialize(v) for k, v in item.items()}}}
    with patch.object(webhooks, 'deliver') as deliver:
        assert webhooks.handler({'Records': [record]}, None) == {'batchItemFailures': []}
        deliver.assert_not_called()
        old = dict(item)
        item['status'] = 'todo'
        record['dynamodb']['OldImage'] = {k: serializer.serialize(v) for k, v in old.items()}
        record['dynamodb']['NewImage'] = {k: serializer.serialize(v) for k, v in item.items()}
        deliver.side_effect = RuntimeError('receiver unavailable')
        assert webhooks.handler({'Records': [record]}, None)['batchItemFailures'] == [{'itemIdentifier': '1'}]
        deliver.side_effect = None
        assert webhooks.handler({'Records': [record]}, None)['batchItemFailures'] == []
        assert json.loads(deliver.call_args.args[1])['type'] == 'task.ready'
        deliver.reset_mock()
        webhooks.handler({'Records': [record]}, None)
        deliver.assert_not_called()


def test_publish_retry_preserves_claim_and_delete_removes_files(api):
    task = api('POST', '/api/tasks', {'status': 'uploading'})[1]
    path = '/api/tasks/' + task['id']
    assert api('PATCH', path, {'status': 'todo', 'publish': True})[0] == 200
    claimed = api('POST', '/api/tasks/claim', {'agent': 'worker'})[1]['task']
    assert api('PATCH', path, {'status': 'todo', 'publish': True})[1]['status'] == 'claimed'
    boto3.client('s3').put_object(Bucket='test-files', Key='alice/' + task['id'] + '/orphan', Body=b'x')
    assert api('DELETE', path)[0] == 200
    assert api('GET', path)[0] == 404
    assert boto3.client('s3').list_objects_v2(Bucket='test-files').get('KeyCount', 0) == 0


def test_jwt_verifies_signature_required_claims_and_token_use(monkeypatch):
    import time
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from types import SimpleNamespace
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv('AUTH_ISSUER', 'https://issuer.example')
    monkeypatch.setenv('AUTH_CLIENT_ID', 'client')
    jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key()))
    monkeypatch.setattr(app, '_jwks', jwks)
    claims = {'sub': 'alice', 'iss': 'https://issuer.example', 'aud': 'client', 'exp': int(time.time()) + 60, 'iat': int(time.time()), 'token_use': 'id'}
    assert app.verify_jwt(jwt.encode(claims, key, algorithm='RS256'))['sub'] == 'alice'
    for invalid in ({**claims, 'aud': 'wrong'}, {**claims, 'token_use': 'access'}, {**claims, 'exp': int(time.time()) - 10}, {k: v for k, v in claims.items() if k != 'sub'}):
        with pytest.raises((jwt.PyJWTError, ValueError)):
            app.verify_jwt(jwt.encode(invalid, key, algorithm='RS256'))


def test_webhook_signature_and_no_redirects():
    import hmac
    from types import SimpleNamespace
    captures = {}
    class Connection:
        def __init__(self, host, address):
            captures['target'] = (host, address)
        def request(self, method, path, body, headers):
            captures.update(method=method, path=path, body=body, headers=headers)
        def getresponse(self):
            return SimpleNamespace(status=302)
        def close(self):
            pass
    hook = {'url': 'https://example.com/hook?x=1', 'secret': 'topsecret'}
    with patch.object(webhooks, 'PinnedHTTPSConnection', Connection), patch.object(socket, 'getaddrinfo', return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]), patch.object(webhooks.time, 'time', return_value=123):
        with pytest.raises(RuntimeError):
            webhooks.deliver(hook, b'{"hello":1}', 'event-1')
    expected = hmac.new(b'topsecret', b'123.{"hello":1}', hashlib.sha256).hexdigest()
    assert captures['headers']['X-SnapTask-Signature'] == 'sha256=' + expected
    assert captures['headers']['X-SnapTask-Event-ID'] == 'event-1'
    assert captures['target'] == ('example.com', '93.184.216.34')


def test_presigned_upload_uses_regional_sigv4_endpoint(api, monkeypatch):
    from urllib.parse import urlsplit, parse_qs
    monkeypatch.setenv('AWS_REGION', 'eu-west-1')
    task = api('POST', '/api/tasks', {'status': 'uploading'})[1]
    status, upload = api('POST', '/api/tasks/' + task['id'] + '/uploads', {'name': 'photo.jpg', 'content_type': 'image/jpeg', 'size': 3})
    assert status == 201
    parsed = urlsplit(upload['upload_url'])
    assert parsed.hostname == 'test-files.s3.eu-west-1.amazonaws.com'
    query = parse_qs(parsed.query)
    assert query['X-Amz-Algorithm'] == ['AWS4-HMAC-SHA256']
    assert '/eu-west-1/s3/aws4_request' in query['X-Amz-Credential'][0]
