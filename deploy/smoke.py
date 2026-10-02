#!/usr/bin/env python3
"""Exercise deployed API with isolated synthetic fixtures, then delete them."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import urllib.error
import urllib.request
import uuid

import boto3
from boto3.dynamodb.conditions import Key

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cli'))
from snaptask import Client


def run(url):
    cloud = boto3.client('cloudformation', region_name='eu-west-1')
    outputs = {x['OutputKey']: x['OutputValue'] for x in cloud.describe_stacks(StackName='snaptask')['Stacks'][0]['Outputs']}
    table = boto3.resource('dynamodb', region_name='eu-west-1').Table(outputs['TableName'])
    owner = 'smoke-' + str(uuid.uuid4())
    token = 'st_' + secrets.token_urlsafe(32)
    token_key = {'PK': 'TOKEN#' + hashlib.sha256(token.encode()).hexdigest(), 'SK': 'META'}
    table.put_item(Item={**token_key, 'owner': owner, 'name': 'temporary smoke fixture'})
    client = Client(url, token)
    try:
        request = urllib.request.Request(url + '/api/tasks')
        try:
            urllib.request.urlopen(request)
            raise AssertionError('Unauthenticated API allowed')
        except urllib.error.HTTPError as exc:
            assert exc.code == 401, exc.code
        staged = client.request('POST', '/api/tasks', {'title': 'Synthetic smoke batch', 'status': 'uploading'})
        tid = staged['id']
        assert client.request('POST', '/api/tasks/claim', {'agent': 'smoke'})['task'] is None
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index in range(2):
                p = Path(directory) / f'test-{index}.txt'
                p.write_text(f'Synthetic SnapTask fixture {index}')
                client.upload(tid, p)
                paths.append(p)
            ready = client.request('PATCH', '/api/tasks/' + tid, {'status': 'todo', 'publish': True})
            assert len(ready['files']) == 2
            claimed = client.request('POST', '/api/tasks/claim', {'agent': 'smoke'})['task']
            assert claimed['id'] == tid
            assert client.request('POST', '/api/tasks/claim', {'agent': 'second'})['task'] is None
            client.request('POST', f'/api/tasks/{tid}/heartbeat', {'agent': 'smoke', 'claim_token': claimed['claim_token']})
            downloaded = client.download(tid, Path(directory) / 'downloaded')
            assert len(downloaded['files']) == 2
            assert {Path(p).read_text() for p in downloaded['files']} == {p.read_text() for p in paths}
            done = client.request('PATCH', '/api/tasks/' + tid, {'status': 'done', 'claim_token': claimed['claim_token'], 'result': 'Smoke checks passed'})
            assert done['status'] == 'done'
            client.request('DELETE', '/api/tasks/' + tid)
        print('PASS: auth, staged batch, two S3 uploads, claim, heartbeat, downloads, completion, deletion')
    finally:
        # Test owner is random and cannot overlap with real users.
        page = table.query(KeyConditionExpression=Key('PK').eq('USER#' + owner))
        with table.batch_writer() as writer:
            for item in page['Items']:
                writer.delete_item(Key={'PK': item['PK'], 'SK': item['SK']})
            writer.delete_item(Key=token_key)
        s3 = boto3.resource('s3', region_name='eu-west-1')
        bucket = s3.Bucket(outputs['BucketName'])
        bucket.objects.filter(Prefix=owner + '/').delete()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://snaptask.dtcdev.click')
    run(parser.parse_args().url.rstrip('/'))
