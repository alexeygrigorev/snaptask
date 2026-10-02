"""At-least-once signed webhook delivery from durable DynamoDB task changes."""
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
import socket
import ssl
import time
import urllib.parse

import boto3
from boto3.dynamodb.types import TypeDeserializer
from backend.app import items, public, json_default, table


def validate_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443):
        raise ValueError('Webhook must be a public HTTPS URL on port 443')
    try:
        addresses = sorted({entry[4][0] for entry in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)})
    except socket.gaierror as exc:
        raise ValueError('Webhook hostname cannot be resolved') from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError('Webhook cannot target private or reserved networks')
    return parsed, addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname, address):
        super().__init__(hostname, timeout=8, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Resolve once, validate every address, then connect to that IP while retaining TLS hostname verification.
        raw = socket.create_connection((self.address, 443), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def deliver(hook, payload, event_id):
    parsed, addresses = validate_url(hook['url'])
    timestamp = str(int(time.time()))
    signature = hmac.new(hook['secret'].encode(), timestamp.encode() + b'.' + payload, hashlib.sha256).hexdigest()
    connection = PinnedHTTPSConnection(parsed.hostname, addresses[0])
    try:
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        connection.request('POST', path, body=payload, headers={'Content-Type': 'application/json', 'User-Agent': 'SnapTask/1.0', 'X-SnapTask-Event-ID': event_id, 'X-SnapTask-Timestamp': timestamp, 'X-SnapTask-Signature': 'sha256=' + signature})
        result = connection.getresponse()
        if not 200 <= result.status < 300:
            raise RuntimeError('Webhook returned ' + str(result.status))
    finally:
        connection.close()


def handler(event, context):
    failures = []
    decoder = TypeDeserializer()
    for record in event.get('Records', []):
        sequence = record['dynamodb'].get('SequenceNumber', record['eventID'])
        try:
            raw = record['dynamodb'].get('NewImage', {})
            item = {k: decoder.deserialize(v) for k, v in raw.items()}
            if not item.get('SK', '').startswith('TASK#') or item.get('status') == 'uploading':
                continue
            old = {k: decoder.deserialize(v) for k, v in record['dynamodb'].get('OldImage', {}).items()}
            kind = 'task.ready' if old.get('status') == 'uploading' else ('task.created' if not old else 'task.updated')
            event_id = record['eventID']
            payload = json.dumps({'id': event_id, 'type': kind, 'task': public(item)}, default=json_default, separators=(',', ':')).encode()
            for hook in items(item['owner'], 'WEBHOOK#'):
                marker = {'PK': 'DELIVERY#' + event_id, 'SK': hook['id']}
                if table().get_item(Key=marker, ConsistentRead=True).get('Item'):
                    continue
                deliver(hook, payload, event_id)
                table().put_item(Item={**marker, 'expires_at': int(time.time()) + 7 * 86400})
        except Exception as exc:
            print(json.dumps({'event_id': record.get('eventID'), 'error_type': type(exc).__name__}))
            failures.append({'itemIdentifier': sequence})
    return {'batchItemFailures': failures}
