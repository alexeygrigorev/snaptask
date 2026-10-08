"""Read Google resources with a token supplied by Dapier token exec.

Standard library only. Tokens remain in the environment, never in output.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service', choices=['drive', 'docs', 'gmail'])
    parser.add_argument('path', help='Relative API resource path')
    parser.add_argument('--param', action='append', default=[], metavar='KEY=VALUE')
    args = parser.parse_args()
    bases = {
        'drive': 'https://www.googleapis.com/drive/v3/',
        'docs': 'https://docs.googleapis.com/v1/',
        'gmail': 'https://gmail.googleapis.com/gmail/v1/',
    }
    if args.path.startswith('/') or '..' in args.path or ':' in args.path or '?' in args.path:
        parser.error('Use a relative resource path and --param for query fields')
    params = dict(value.split('=', 1) for value in args.param)
    token = os.environ.get('DAPIER_ACCESS_TOKEN')
    if not token:
        parser.error('Run through dapier token exec; DAPIER_ACCESS_TOKEN is missing')
    url = bases[args.service] + args.path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        print(f'Google {args.service} returned HTTP {error.code}', file=sys.stderr)
        try:
            detail = json.load(error).get('error', {}).get('message', '')
            print(detail, file=sys.stderr)
        except (ValueError, AttributeError):
            pass
        return 1
    except urllib.error.URLError:
        print('Google API could not be reached', file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
