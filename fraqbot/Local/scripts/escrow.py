import logging

from Local.helpers.sql import Table


def add_paid_field(db, table_name, table_cfg):
    completed = False
    try:
        paid = [t for t in table_cfg if t['name'] == 'paid'][0]
        table_cfg = [t for t in table_cfg if t['name'] != 'paid']
        table = Table(table_name, table_cfg, db.engine)
        records = table.query(sort={'field': 'id'})
        table.table.__table__.drop(db.engine)
        table_cfg.append(paid)
        table = Table(table_name, table_cfg, db.engine)

        latest_group = db.pool_history.query(
            limit=1,
            sort={'field': 'id', 'direction': 'desc'},
            return_field_value='id'
        )
        latest_group = str(latest_group) if latest_group else ''

        for record in records:
            if record['escrow_group_id'] != latest_group:
                record['paid'] = True

        table.bulk_insert(records)
        completed = True
    except Exception as e:
        msg = f'Error running add_paid_field migration:\n{e}'
        logging.getLogger().error(msg)

    return completed, table