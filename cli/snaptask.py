#!/usr/bin/env python3
"""SnapTask API client (Python standard library)."""
import argparse
import getpass
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'snaptask' / 'config.json'


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream: stream.write(content)
        Path(temporary).replace(path)
    finally:
        if Path(temporary).exists(): Path(temporary).unlink()


class Client:
    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.token = token

    def request(self, method, path, data=None, extra_headers=None):
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json'}
        headers.update(extra_headers or {})
        if data is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(data).encode()
        request = urllib.request.Request(self.url + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
        return json.loads(payload) if payload else {}

    def upload(self, task_id, filename):
        path = Path(filename)
        content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        content = path.read_bytes()
        key = hashlib.sha256(path.name.encode() + b'\0' + content).hexdigest()
        result = self.request('POST', f'/api/tasks/{task_id}/uploads', {
            'name': path.name, 'content_type': content_type, 'size': len(content)},
            extra_headers={'Idempotency-Key': key})
        if result.get('completed'):
            return {'file_id': result['file_id'], 'completed': True}
        request = urllib.request.Request(result['upload_url'], data=content,
                                         headers={'Content-Type': content_type}, method='PUT')
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read()
        return self.request('POST', f'/api/tasks/{task_id}/uploads/{result["file_id"]}/complete', {})

    def download(self, task_id, directory):
        details = self.request('GET', '/api/tasks/' + urllib.parse.quote(task_id, safe=''))
        task = details.get('task', details)
        files = task.get('files', details.get('files', []))
        directory = Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        downloaded = []
        for item in files:
            file_id = str(item['id'])
            if Path(file_id).name != file_id or file_id in ('.', '..'):
                raise ValueError('Unsafe file ID returned by server')
            name = Path(item.get('name', 'attachment')).name
            target = directory / (file_id + '-' + name)
            if target.is_symlink():
                raise ValueError('Refusing to replace symlink: ' + str(target))
            signed = self.request('GET', '/api/tasks/' + urllib.parse.quote(task_id, safe='') + '/files/' + urllib.parse.quote(file_id, safe=''))
            with urllib.request.urlopen(signed['download_url'], timeout=120) as response:
                atomic_write(target, response.read())
            item['local_path'] = target.name
            downloaded.append(str(target))
        task['files'] = files
        atomic_write(directory / 'task.json', (json.dumps(task, indent=2) + '\n').encode())
        return {'task_id': task_id, 'directory': str(directory), 'files': downloaded}



def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', help='Server URL (or SNAPTASK_URL)')
    commands = p.add_subparsers(dest='command', required=True)
    for name in ('login', 'configure'):
        c = commands.add_parser(name, help='Save a web-created API token securely on disk')
        c.add_argument('--token-stdin', action='store_true')
    tasks = commands.add_parser('tasks').add_subparsers(dest='action', required=True)
    tasks.add_parser('list')
    create = tasks.add_parser('create')
    create.add_argument('title'); create.add_argument('--notes', default='')
    show = tasks.add_parser('show'); show.add_argument('id')
    delete = tasks.add_parser('delete'); delete.add_argument('id')
    update = tasks.add_parser('update'); update.add_argument('id')
    update.add_argument('--title'); update.add_argument('--notes'); update.add_argument('--claim-token'); update.add_argument('--publish', action='store_true', default=None)
    update.add_argument('--status', choices=['todo', 'claimed', 'done'])
    upload = commands.add_parser('upload', help='Create one grouped task or attach files to a task')
    upload.add_argument('files', nargs='+'); upload.add_argument('--task'); upload.add_argument('--title')
    download = commands.add_parser('download'); download.add_argument('id'); download.add_argument('--directory', required=True)
    claim = commands.add_parser('claim'); claim.add_argument('--agent', required=True)
    heartbeat = commands.add_parser('heartbeat'); heartbeat.add_argument('id'); heartbeat.add_argument('--agent', required=True); heartbeat.add_argument('--claim-token', required=True)
    complete = commands.add_parser('complete'); complete.add_argument('id'); complete.add_argument('--result', default=''); complete.add_argument('--claim-token', required=True)
    tokens = commands.add_parser('tokens').add_subparsers(dest='action', required=True)
    tokens.add_parser('list'); tc = tokens.add_parser('create'); tc.add_argument('name')
    tr = tokens.add_parser('revoke'); tr.add_argument('id')
    hooks = commands.add_parser('webhook').add_subparsers(dest='action', required=True)
    hooks.add_parser('list'); hc = hooks.add_parser('add'); hc.add_argument('webhook_url')
    hd = hooks.add_parser('delete'); hd.add_argument('id')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    config = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    url = args.url or os.environ.get('SNAPTASK_URL') or config.get('url', 'https://snaptask.dtcdev.click')
    if args.command in ('login', 'configure'):
        token = sys.stdin.readline().strip() if args.token_stdin else getpass.getpass('API token from web Settings: ')
        if not token: raise ValueError('Token cannot be empty')
        CONFIG.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Open restrictive before writing so token is never briefly world-readable.
        fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as stream: json.dump({'url': url, 'token': token}, stream)
        print('Configured ' + url); return
    token = os.environ.get('SNAPTASK_TOKEN') or config.get('token')
    if not token: raise ValueError('Run snaptask login or set SNAPTASK_TOKEN')
    client = Client(url, token)
    if args.command == 'tasks':
        if args.action == 'list': result = client.request('GET', '/api/tasks')
        elif args.action == 'delete': result = client.request('DELETE', '/api/tasks/' + args.id)
        elif args.action == 'show': result = client.request('GET', '/api/tasks/' + args.id)
        elif args.action == 'create': result = client.request('POST', '/api/tasks', {'title': args.title, 'notes': args.notes})
        else: result = client.request('PATCH', '/api/tasks/' + args.id, {k: getattr(args, k) for k in ('title', 'notes', 'status', 'claim_token', 'publish') if getattr(args, k) is not None})
    elif args.command == 'upload':
        for filename in args.files:
            if not Path(filename).is_file(): raise ValueError('Not a file: ' + filename)
            if Path(filename).stat().st_size == 0: raise ValueError('File is empty: ' + filename)
            if Path(filename).stat().st_size > 25 * 1024 * 1024: raise ValueError('File exceeds 25 MiB: ' + filename)
        task_id = args.task
        if not task_id:
            created = client.request('POST', '/api/tasks', {'title': args.title or Path(args.files[0]).name, 'notes': '', 'status': 'uploading'})
            task_id = created.get('task', created)['id']
        print('Uploading task ' + task_id, file=sys.stderr)
        result = {'task_id': task_id, 'files': [client.upload(task_id, path) for path in args.files]}
        if not args.task: client.request('PATCH', '/api/tasks/' + task_id, {'status': 'todo', 'publish': True})
    elif args.command == 'download': result = client.download(args.id, args.directory)
    elif args.command == 'claim': result = client.request('POST', '/api/tasks/claim', {'agent': args.agent})
    elif args.command == 'heartbeat': result = client.request('POST', '/api/tasks/' + args.id + '/heartbeat', {'agent': args.agent, 'claim_token': args.claim_token})
    elif args.command == 'complete': result = client.request('PATCH', '/api/tasks/' + args.id, {'status': 'done', 'result': args.result, 'claim_token': args.claim_token})
    elif args.command in ('tokens', 'webhook'):
        path = '/api/' + ('tokens' if args.command == 'tokens' else 'webhooks')
        if args.action == 'list': result = client.request('GET', path)
        elif args.action in ('delete', 'revoke'): result = client.request('DELETE', path + '/' + args.id)
        else: result = client.request('POST', path, {'name': args.name} if args.command == 'tokens' else {'url': args.webhook_url})
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt: pass
    except (urllib.error.URLError, ValueError, KeyError, OSError) as exc:
        print('snaptask: ' + str(exc), file=sys.stderr); sys.exit(1)
