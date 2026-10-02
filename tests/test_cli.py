import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

spec = importlib.util.spec_from_file_location('snaptask_cli', Path(__file__).parents[1] / 'cli/snaptask.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class CLITest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / 'config/config.json'
        self.patches = [patch.object(cli, 'CONFIG', self.config), patch.dict(os.environ, {'SNAPTASK_TOKEN': 'st_test'}, clear=True)]
        for p in self.patches: p.start(); self.addCleanup(p.stop)

    def run_cli(self, args):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            cli.main(args)
        return output.getvalue()

    def test_pairing_permissions(self):
        with patch('sys.stdin', io.StringIO('st_private\n')):
            self.run_cli(['login', '--token-stdin'])
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.config.read_text())['token'], 'st_private')

    def test_batch_only_published_after_uploads(self):
        files = [Path(self.temp.name) / name for name in ('one.jpg', 'two.jpg')]
        for path in files: path.write_bytes(b'image')
        with patch.object(cli.Client, 'request', return_value={'id': 'task1'}) as request, patch.object(cli.Client, 'upload', return_value={}) as upload:
            result = json.loads(self.run_cli(['upload', '--title', 'Batch', *map(str, files)]))
            self.assertEqual(request.call_args_list[0].args, ('POST', '/api/tasks', {'title': 'Batch', 'notes': '', 'status': 'uploading'}))
            self.assertEqual(request.call_args_list[-1].args, ('PATCH', '/api/tasks/task1', {'status': 'todo', 'publish': True}))
            self.assertEqual(upload.call_count, 2)
            self.assertEqual(result['task_id'], 'task1')

    def test_failed_batch_is_not_published(self):
        path = Path(self.temp.name) / 'one.jpg'; path.write_bytes(b'image')
        with patch.object(cli.Client, 'request', return_value={'id': 'task1'}) as request, patch.object(cli.Client, 'upload', side_effect=OSError('offline')):
            with self.assertRaises(OSError): self.run_cli(['upload', str(path)])
            self.assertEqual(request.call_count, 1)

    def test_missing_file_does_not_create_task(self):
        with patch.object(cli.Client, 'request') as request:
            with self.assertRaises(ValueError): self.run_cli(['upload', '/absent/image.jpg'])
            request.assert_not_called()

    def test_webhook_url_not_used_as_server_url(self):
        with patch.object(cli.Client, 'request', return_value={}) as request:
            self.run_cli(['webhook', 'add', 'https://receiver.example/hook'])
            request.assert_called_once_with('POST', '/api/webhooks', {'url': 'https://receiver.example/hook'})

    def test_claim_agent_contract(self):
        with patch.object(cli.Client, 'request', return_value={'task': None}) as request:
            self.assertEqual(json.loads(self.run_cli(['claim', '--agent', 'agent-1'])), {'task': None})
            request.assert_called_once_with('POST', '/api/tasks/claim', {'agent': 'agent-1'})

    def test_download_uses_safe_names_and_metadata(self):
        client = cli.Client('https://server.example', 'st_test')
        details = {'task': {'id': 'task1', 'title': 'Batch'}, 'files': [{'id': 'file1', 'name': '../../photo.jpg'}]}
        response = MagicMock(); response.__enter__.return_value.read.return_value = b'picture'
        with patch.object(client, 'request', side_effect=[details, {'download_url': 'https://storage.example/file'}]), patch.object(cli.urllib.request, 'urlopen', return_value=response):
            result = client.download('task1', self.temp.name)
        self.assertEqual((Path(self.temp.name) / 'file1-photo.jpg').read_bytes(), b'picture')
        self.assertEqual(json.loads((Path(self.temp.name) / 'task.json').read_text())['files'][0]['local_path'], 'file1-photo.jpg')
        self.assertEqual(len(result['files']), 1)

    def test_download_rejects_traversal_id(self):
        client = cli.Client('https://server.example', 'st_test')
        with patch.object(client, 'request', return_value={'id': 'task1', 'files': [{'id': '../escape', 'name': 'photo'}]}):
            with self.assertRaises(ValueError): client.download('task1', self.temp.name)

    def test_heartbeat_preserves_claim_ownership(self):
        with patch.object(cli.Client, 'request', return_value={}) as request:
            self.run_cli(['heartbeat', 'task1', '--agent', 'worker', '--claim-token', 'lease1'])
            request.assert_called_once_with('POST', '/api/tasks/task1/heartbeat', {'agent': 'worker', 'claim_token': 'lease1'})

    def test_completion_includes_claim_token(self):
        with patch.object(cli.Client, 'request', return_value={}) as request:
            self.run_cli(['complete', 'task1', '--claim-token', 'lease1', '--result', 'Processed'])
            request.assert_called_once_with('PATCH', '/api/tasks/task1', {'status': 'done', 'result': 'Processed', 'claim_token': 'lease1'})

    def test_release_includes_claim_token(self):
        with patch.object(cli.Client, 'request', return_value={}) as request:
            self.run_cli(['tasks', 'update', 'task1', '--status', 'todo', '--claim-token', 'lease1'])
            request.assert_called_once_with('PATCH', '/api/tasks/task1', {'status': 'todo', 'claim_token': 'lease1'})

    def test_upload_retry_reuses_key_and_skips_completed(self):
        path = Path(self.temp.name) / 'image.jpg'; path.write_bytes(b'image')
        client = cli.Client('https://server.example', 'st_test')
        with patch.object(client, 'request', return_value={'file_id': 'file1', 'completed': True}) as request, patch.object(cli.urllib.request, 'urlopen') as network:
            client.upload('task1', path)
            first = request.call_args.kwargs['extra_headers']['Idempotency-Key']
            client.upload('task1', path)
            self.assertEqual(first, request.call_args.kwargs['extra_headers']['Idempotency-Key'])
            network.assert_not_called()

    def test_request_sends_bearer_header(self):
        response = MagicMock(); response.__enter__.return_value.read.return_value = b'{"tasks":[]}'
        with patch.object(cli.urllib.request, 'urlopen', return_value=response) as call:
            result = cli.Client('https://server.example/', 'st_secret').request('GET', '/api/tasks')
            request = call.call_args.args[0]
            self.assertEqual(request.get_header('Authorization'), 'Bearer st_secret')
            self.assertEqual(request.full_url, 'https://server.example/api/tasks')
            self.assertEqual(result, {'tasks': []})


if __name__ == '__main__': unittest.main()
