import logging

from Local.helpers.sql import Table


def add_completed_field(db, table_name, table_cfg):
    completed = False

    try:
        completed = [t for t in table_cfg if t['name'] == 'completed'][0]
        table_cfg = [t for t in table_cfg if t['name'] != 'completed']
        table = Table(table_name, table_cfg, db.engine)
        records = table.query(sort={'field': 'id'})
        table.table.__table__.drop(db.engine)
        table_cfg.append(completed)
        table = Table(table_name, table_cfg, db.engine)

        for i, record in enumerate(records):
            if i != len(records) - 1:
                record['completed'] = True

        table.bulk_insert(records)
        completed = True
    except Exception as e:
        msg = f'Error running add_completed_field migraction:\n{e}'
        logging.getLogger().error(msg)

    return completed, table
