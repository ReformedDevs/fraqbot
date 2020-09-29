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
