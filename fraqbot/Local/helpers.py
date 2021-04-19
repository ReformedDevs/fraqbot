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


LOGGER = logging.getLogger('helpers')


def now():
    return int(round(time.time()))


def load_file(path, f_type=None, raw=None, delimiter=None):
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

    except Exception as e:
        LOGGER.error(e)
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
        LOGGER.error(e)
        return None


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
            if data.strip() == 'None':
                data = None

        return data


def jsearch(transform, data):
    return jmespath.search(
        transform,
        data,
        options=jmespath.Options(custom_functions=CustomFunctions())
    )


def snake_to_pascal(item):
    if not isinstance(item, str):
        return item

    out = []
    for word in re.split(r'[A-Z_]', item):
        if len(word) == 1:
            out.append(word.upper())
        else:
            out.append('{}{}'.format(word[0].upper(), word[1:].lower()))

    return ''.join(out)


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
