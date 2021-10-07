
import csv
import json
import logging
import os
import re

from jsonschema import validate
import yaml


LOGGER = logging.getLogger('helpers.file')


def load_file(path, f_type=None, raw=None, delimiter=None, default=None,
              split_lines=False):
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
