import json
import logging
import time

import requests
import yaml


def now():
    return int(round(time.time()))


def load_file(path, f_type=None):
    try:
        with open(path) as f:
            data = f.read()

        if f_type == 'json':
            data = json.loads(data)
        elif f_type == 'yaml':
            data = yaml.safe_load(data)

    except Exception as e:
        logging.error(e)
        return None

    return data


def write_file(path, data, f_type=None):
    try:
        with open(path, 'w') as f:
            if f_type == 'json':
                json.dump(data, f, indent=2, sort_keys=True)
            elif f_type == 'yaml':
                yaml.safe_dump(data, f, sort_keys=True)
            else:
                f.write(data)

        return True
    except Exception as e:
        logging.error(e)
        return None


def call_rest_api(caller, method, url, payload=None, convert_payload=None,
                  headers=None, params=None, response=None, default=None):
    method_map = {
        'get': requests.get,
        'post': requests.post
    }

    if method not in method_map:
        logging.error(f'Invalid method from {caller} to {url}:\n{method}')
        return None

    request_args = {}
    if payload:
        if convert_payload and convert_payload in ['json', yaml]:
            if convert_payload == 'json':
                payload = json.dumps(payload)
            elif convert_payload == 'yaml':
                payload = yaml.safe_dump(payload)

        request_args['data'] = payload

    if headers:
        request_args['headers'] = headers

    if params:
        request_args['params'] = params

    try:
        api_call = method_map[method](url, **request_args)
        if str(api_call.status_code).startswith('2'):
            res = api_call.text
            if response:
                if response == 'json':
                    res = json.loads(res)
                elif response == 'yaml':
                    res = yaml.safe_load(res)

            return res

        else:
            logging.error(f'{api_call.status_code}: {api_call.text}')
            return default
    except Exception as e:
        logging.error(str(e))
        return default


def format_table(data, fields=None, margin=None, sep=None, border=None):
    if not fields or not isinstance(fields, list):
        field_order = sorted(data[0].keys())
        fields = {f: {} for f in field_order}
    else:
        field_order = [f['field'] for f in fields]
        fields = {f['field']: f for f in fields}

    data.insert(0, {
        f: fields.get(f, {}).get('display', f)
        for f in field_order
    })

    for f, info in fields.items():
        info['max'] = max(len(str(d.get(f, ''))) for d in data)

    margin = margin if margin and isinstance(margin, int) else 0
    sep = sep if sep and isinstance(sep, str) else ''
    border = border if border and isinstance(border, str) else ''

    lines = []
    for d in data:
        line = []
        for f in field_order:
            item = str(d.get(f, ''))
            while len(item) < fields[f]['max']:
                item = f'{item} '

            for _ in range(margin):
                item = f' {item} '

            line.append(item)

        line = f'{border}{sep.join(line)}{border}'

        lines.append(line)

    if border:
        border_line = ''
        for _ in range(len(lines[0])):
            border_line = f'{border_line}{border}'

        lines.insert(0, border_line)
        lines.insert(2, border_line)
        lines.append(border_line)

    return '\n'.join(lines)
