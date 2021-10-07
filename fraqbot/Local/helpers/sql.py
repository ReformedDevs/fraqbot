from copy import deepcopy
from importlib import import_module
import logging
import os
import sys

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Float
from sqlalchemy import inspect
from sqlalchemy import Integer
from sqlalchemy.orm import Query
from sqlalchemy.orm import Session
from sqlalchemy import String


LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(LOCAL_DIR)
SCRIPTS_DIR = os.path.join(LOCAL_DIR, '..', 'scripts')
sys.path.append(SCRIPTS_DIR)


from file import load_file  # noqa: E402
from file import validate_schema  # noqa: E402
from text import snake_to_pascal  # noqa: E402
from utils import jsearch  # noqa: E402


TYPES = {
    'string': String,
    'int': Integer,
    'float': Float,
    'boolean': Boolean
}

MIGRATION_TABLE = {
    'migration': [
        {
            'name': 'id',
            'type': 'string',
            'kwargs': {
                'primary_key': True
            }
        },
        {
            'name': 'completed',
            'type': 'boolean',
            'kwargs': {
                'default': False
            }
        }
    ]
}


class Table(object):
    def __init__(self, name, columns, engine):
        validate_schema(
            columns,
            schema_file=os.path.join(
                LOCAL_DIR, '..', 'data', 'schemas', 'sql_table.yaml'),
            raise_ex=True
        )
        self.name = name
        self.logger = logging.getLogger(f'Table: {snake_to_pascal(self.name)}')
        self.engine = engine
        self._build_table(columns)
        self.errors = []

    def _build_table(self, columns):
        base = declarative_base()
        cls_name = snake_to_pascal(self.name)
        cfg = {'__tablename__': self.name}
        for column in columns:
            _type = TYPES.get(column['type'], String)
            _type_args = column.get('type_args', [])

            if _type_args:
                _type = _type(*_type_args)

            kwargs = column.get('kwargs', {})
            cfg[column['name']] = Column(_type, **kwargs)

        self.table = type(cls_name, (base, ), cfg)
        base.metadata.create_all(self.engine)
        self.pks = [f.key for f in inspect(self.table).primary_key]
        self.fields = [k for k in cfg.keys() if k != '__tablename__']

    def _error(self, name=None, raise_ex=False):
        if self.errors:
            if raise_ex is True:
                raise Exception(f'Error(s) on {name} method: {self.errors}')
            else:
                for e in self.errors:
                    self.logger.error(f'Error on {name} method: {e}')

            self.errors = []

    def _deserialize(self, query_result, fields=None):
        def _deserialize_item(item, keys):
            return {
                k: getattr(item, k, None)
                for k in keys
            }

        fields = self._validate_fields(fields)

        if isinstance(query_result, list):
            return [_deserialize_item(q, fields) for q in query_result]
        elif query_result:
            return _deserialize_item(query_result, fields)
        else:
            return query_result

    def _validate_fields(self, fields):
        if isinstance(fields, str):
            fields = [f.strip() for f in fields.split(',')]
        elif not fields or not isinstance(fields, (list, tuple)):
            return self.fields

        invalid = [f for f in fields if f not in self.fields]
        self.errors += [f'{f} is not a valid field.' for f in invalid]

        return [f for f in fields if f in self.fields]

    def _generate_filter(self, query, _filter):
        if not _filter:
            return query

        def add_args(_filter, args=None, key=None):
            if not args:
                args = []

            column = getattr(self.table, key) if key else None
            if key and key not in self.fields:
                self.errors.append(
                    f'{key} is not a valid field for filtering.')

                return args

            if isinstance(_filter, dict):
                if not key:
                    for k, v in _filter.items():
                        _key = k[:-4] if k.endswith('__op') else k
                        args = add_args(v, args, _key)
                else:
                    for k, v in _filter.items():
                        args.append(getattr(column.comparator, k)(v))

            else:
                args.append(getattr(column.comparator, '__eq__')(_filter))

            return args

        args = add_args(_filter)

        return query.filter(*args)

    def _select_fields(self, query, fields):
        fields = self._validate_fields(fields)
        args = [
            getattr(self.table, field)
            for field in fields
        ]

        return query.add_columns(*args)

    def _sort_query(self, query, sort):
        direction = 'asc'
        err = f'Invalid sort in query: {sort}'

        if isinstance(sort, dict):
            field = sort.get('field')
            direction = sort.get('direction', direction).lower()
        elif isinstance(sort, str):
            sort = [s.strip() for s in sort.split(',')]
            field = sort[0]
            direction = sort[1].lower() if len(sort) > 1 else direction
        else:
            self.errors.append(err)
            return query

        if not field or field not in self.fields:
            self.errors.append(err)
            return query

        field = getattr(self.table, field)
        direction = getattr(field, direction)

        return query.order_by(direction())

    def _validate_limit(self, limit):
        err = f'Invalid query limit: {limit}'

        if limit in [None, 'all']:
            return 'all'

        if isinstance(limit, int) and limit > 0:
            return limit

        self.errors.append(err)

        return 'all'

    def _get(self, ids, session=None, ignore_err=False):
        err = 'Not all primary keys provided.'
        pks = None

        if isinstance(ids, dict):
            if all([pk in ids for pk in self.pks]):
                pks = tuple(ids[pk] for pk in self.pks)
        elif isinstance(ids, (list, tuple)):
            if len(self.pks) == len(ids):
                pks = tuple(pk for pk in ids)
        elif isinstance(ids, str):
            pks = tuple(pk.strip() for pk in ids.split(','))
            if len(self.pks) != len(pks):
                pks = None
        elif len(self.pks) == 1:
            pks = (ids, )

        if not pks:
            if not ignore_err:
                self.errors.append(err)

            return None

        if session:
            return session.get(self.table, pks)

        with Session(self.engine) as session:
            return session.get(self.table, pks)

    def get(self, ids, fields=None, raise_ex=False, return_field_value=None):
        data = self._get(ids)
        if not data:
            return None

        try:
            data = self._deserialize(data, fields)
            if return_field_value:
                data = data.get(return_field_value)

        except Exception as e:
            data = None
            self.errors.append(e)

        self._error('get', raise_ex)

        return data

    def query(self, fields=None, _filter=None, sort=None, limit=None,
              raise_ex=False, return_field_value=None):
        if return_field_value and limit and limit == 1:
            fields = return_field_value

        query = Query(self.table)
        query = self._generate_filter(query, _filter) if _filter else query
        query = self._select_fields(query, fields) if fields else query
        query = self._sort_query(query, sort) if sort else query
        limit = self._validate_limit(limit)

        with Session(self.engine) as session:
            if isinstance(limit, int):
                if limit == 1:
                    data = query.with_session(session).limit(1).all()
                    data = data[0] if data else {}
                else:
                    data = query.with_session(session).limit(limit).all()
            else:
                data = query.with_session(session).all()

        self._error('query', raise_ex)

        data = self._deserialize(data, fields)
        if limit == 1 and return_field_value and data:
            data = data.get(return_field_value)

        return data

    def upsert(self, record, raise_ex=False):
        ok = False
        try:
            with Session(self.engine) as session:
                current = self._get(record, session, ignore_err=True)
                if current:
                    for field, value in record.items():
                        if field not in self.pks:
                            setattr(current, field, value)

                else:
                    item = self.table(**record)
                    session.add(item)

                session.commit()

            ok = True
        except Exception as e:
            self.errors.append(f'Error upserting {record}: {e}')

        self._error('upsert', raise_ex)

        return ok

    def bulk_insert(self, records, raise_ex=False):
        ok = False

        if isinstance(records, dict):
            records = [records]

        if not isinstance(records, list):
            self.errors.append(f'Invalid bulk insert payload: {records}')
        else:
            try:
                items = [self.table(**record) for record in records]
                with Session(self.engine) as session:
                    session.bulk_save_objects(items)
                    session.commit()

                ok = True
            except Exception as e:
                self.errors.append(f'Error on bulk insert: {e}')

        self._error('bulk_insert', raise_ex)

        return ok

    def count(self, raise_ex=False):
        out = None
        try:
            with Session(self.engine) as session:
                out = Query(self.table, session=session).count()

        except Exception as e:
            self.errors.append(f'Error getting count: {e}')

        self._error('count', raise_ex)

        return out


class DB(object):
    def __init__(self, _type, path=None, tables=None, seeds=None,
                 migrations=None):
        _tables = deepcopy(MIGRATION_TABLE)
        tables = {} if not isinstance(tables, dict) else tables
        _tables.update(tables)
        seeds = {} if not isinstance(seeds, dict) else seeds
        migrations = {} if not isinstance(migrations, dict) else migrations
        validate_schema(
            {'tables': _tables, 'seeds': seeds, 'migrations': migrations},
            schema_file=os.path.join(
                LOCAL_DIR, '..', 'data', 'schemas', 'sql_db.yaml'),
            raise_ex=True
        )

        self.engine = create_engine(f'sqlite:///{path}')
        self.tables = []

        for name, columns in _tables.items():
            setattr(self, name, Table(name, columns, self.engine))
            self.tables.append(name)

        self.process_seeds(seeds)
        self.process_migrations(migrations, _tables)

    def get_migration_state(self, _id):
        state = self.migration.get(_id, return_field_value='completed')
        if not isinstance(state, bool):
            state = False

        return state

    def process_migrations(self, migrations, tables):
        for table_name, migr_set in migrations.items():
            for migration in migr_set:
                try:
                    script_id = migration['id']
                    migration_id = f'{table_name}-{script_id}'
                    completed = self.get_migration_state(migration_id)

                    if completed:
                        continue

                    module = import_module(table_name)
                    script = getattr(module, script_id)
                    completed, table = script(
                        self, table_name, tables[table_name])
                    setattr(self, table_name, table)
                    self.migration.upsert(
                        {'id': migration_id, 'completed': completed})
                except Exception as e:
                    print(e)

    def process_seeds(self, seeds):
        insert = None
        if seeds:
            for table_name, info in seeds.items():
                if table_name in self.tables:
                    table = getattr(self, table_name)

                    if table.count() == 0:
                        if isinstance(info, list):
                            insert = table.bulk_insert(info)
                        elif isinstance(info, dict):
                            if 'file' in info:
                                load_kwargs = info.get('load_kwargs', {})
                                data = load_file(info['file'], **load_kwargs)
                            else:
                                data = info.get('data', [])

                            transform = info.get('transform')
                            if transform:
                                data = jsearch(transform, data)

                            insert = table.bulk_insert(data)

        return insert
