import csv
import json
import logging
import os
import re
import time

import jmespath
from jmespath import functions
from jsonschema import validate
import requests
import yaml


LOGGER = logging.getLogger('helpers.utils')


def now():
    return int(round(time.time()))


def call_slack_api(client, method, get_all, transform, **kwargs):
    out = []
    total_limit = kwargs.pop('total_limit', 3000)

    while True:
        data = client.api_call(method, **kwargs)
        if not data:
            break

        if not get_all:
            out = jsearch(transform, data) if transform else None
            break

        temp = jsearch(transform, data)
        if not temp:
            break

        out += temp
        next_cursor = jsearch('response_metadata.next_cursor', data)
        if not next_cursor or len(out) >= total_limit:
            break

        kwargs['cursor'] = next_cursor

    return out


def call_rest_api(caller, method, url, payload=None, convert_payload=None,
                  headers=None, params=None, response=None, default=None):
    method_map = {
        'get': requests.get,
        'post': requests.post
    }

    if method not in method_map:
        LOGGER.error(f'Invalid method from {caller} to {url}:\n{method}')
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
            LOGGER.error(f'{api_call.status_code}: {api_call.text}')
            return default
    except Exception as e:
        LOGGER.error(str(e))
        return default


class CustomFunctions(functions.Functions):
    @functions.signature(
        {'types': ['object']}, {'types': ['string']}, {'types': ['string']})
    def _func_key_val_to_fields(self, data, key_field, val_field):
        return [
            {key_field: key, val_field: val}
            for key, val in data.items()
        ]

    @functions.signature({'types': ['string', 'null']})
    def _func_string_or_null(self, data):
        if isinstance(data, str):
            if data.strip() in ['None', 'null']:
                data = None

        return data

    @functions.signature(
        {'types': ['boolean', 'array', 'object', 'null', 'string',
                   'number', 'expref']},
        {'types': ['boolean', 'array', 'object', 'null', 'string',
                   'number', 'expref']},
        {'types': ['boolean']})
    def _func_val_or_val(self, val1, val2, condition):
        if condition:
            return val1
        else:
            return val2

    @functions.signature({'types': ['string']})
    def _func_lower(self, value):
        return value.lower()

    @functions.signature(
        {'types': ['string']},
        {'types': ['string']},
        {'types': ['number']})
    def _func_split_items(self, value, _split, count):
        if count < 1:
            return value

        items = [v.strip() for v in value.split(_split)]
        if len(items) <= count:
            return value

        return ' '.join(items[:count])

    @functions.signature(
        {'types': ['string']},
        {'types': ['string']},
        {'types': ['string']})
    def _func_str_replace(self, text, srch, repl):
        return text.replace(srch, repl)


def jsearch(transform, data):
    return jmespath.search(
        transform,
        data,
        options=jmespath.Options(custom_functions=CustomFunctions())
    )


def set_properties(cls, properties, source_file):
    for property in properties:
        if not isinstance(property, dict) or 'name' not in property:
            continue

        if 'file' in property:
            file_atts = property['file']
            path = os.path.join(
                os.path.abspath(os.path.dirname(source_file)),
                file_atts.pop('path', '')
            )
            value = load_file(path, **file_atts)
        else:
            value = property.get('data')

        setattr(cls, property['name'], value)


def load_file(path, f_type=None, raw=None, delimiter=None, default=None,
              split_lines=False, transform=None):
    if not f_type:
        if path.endswith('.json'):
            f_type = 'json'
        elif path.endswith('.yaml'):
            f_type = 'yaml'
        elif path.endswith('.csv'):
            f_type = 'csv'

    try:
        with open(path) as f:
            data = f.read()

        if raw is not True:
            if f_type == 'json':
                data = json.loads(data)
            elif f_type == 'yaml':
                data = yaml.safe_load(data)
            elif f_type == 'csv':
                data = [
                    row for row in
                    csv.DictReader(data.splitlines(), delimiter=delimiter)
                ]

            if transform and data:
                data = jsearch(transform, data)

    except Exception as e:
        LOGGER.error(e)
        return default

    if split_lines is True and isinstance(data, str):
        data = data.splitlines()

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
        LOGGER.error(e)
        return None


def load_schema(schema_file):
    schema = load_file(schema_file)
    raw_schema = yaml.safe_dump(schema)
    defs = {}
    files = {}
    for match in re.finditer(r'\$file:\s(.*(.yaml|.json))', raw_schema):
        f_name = match.group(1)
        if f_name not in files:
            files[f_name] = {
                'prefix': ''.join(f_name.split('/')[-1].split('.')[:-1]),
                'ref': match.group(0)
            }

    for f_name, info in files.items():
        prefix = info['prefix']
        if f_name.startswith('/'):
            path = f_name
        else:
            path = os.path.join(
                os.path.abspath(os.path.dirname(schema_file)),
                f_name
            )

        ref_schema = yaml.safe_dump(load_schema(path))
        ref_schema = ref_schema.replace('#/$defs', f'#/$defs/{prefix}')
        ref_schema = yaml.safe_load(ref_schema)
        defs[prefix] = ref_schema.pop('$defs', {})
        defs[prefix]['_main'] = ref_schema
        raw_schema = raw_schema.replace(
            info['ref'], f"$ref: '#/$defs/{prefix}/_main'")

    if files:
        schema = yaml.safe_load(raw_schema)
        if '$defs' not in schema:
            schema['$defs'] = {}

        schema['$defs'].update(defs)

    return schema


def validate_schema(data, schema=None, schema_file=None, raise_ex=False):
    out = False
    errors = []

    if not schema and not schema_file:
        errors.append('No schema provided for validation.')
    else:
        try:
            if schema_file:
                schema = load_schema(schema_file)

            validate(data, schema)
            out = True
        except Exception as e:
            errors.append(e)

    if errors:
        msg = f'Schema validation error(s): {errors}'

        if raise_ex is True:
            raise Exception(msg)
        else:
            LOGGER.error(msg)

    return out
