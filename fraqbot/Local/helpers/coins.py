from copy import copy
import logging
import os

from Legobot.Connectors.Slack import Slack
from Legobot.Lego import Lego

from helpers import file
from helpers.sql import DB
from helpers import utils

LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')
LOGGER = logging.getLogger(__name__)
DEFAULTS = {
    'name': 'Coins',
    'starting_value': 20,
    'triggers': ['!coins']
}


class CoinsBase(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))

        self._set_bot_thread()
        self._set_defaults(kwargs)
        for prop in ['secret_word_channels', 'disbursement_channels']:
            if hasattr(self, prop):
                setattr(self,  prop, [
                    self.botThread.get_channel_id_by_name(channel)
                    for channel in getattr(self, prop)
                ])

        # set tx locations and load/initialize db
        tables = {}
        table_dir = os.path.join(LOCAL_DIR, 'data', 'tables')
        for _file in os.listdir(table_dir):
            path = os.path.join(table_dir, _file)
            if os.path.isfile(path):
                tables.update(file.load_file(path))

        self._init_tx_db(tables, kwargs.get('seeds', {}))

    # Init Methods
    def _init_tx_db(self, tables, seeds):
        self.tx_dir = os.path.join(LOCAL_DIR, 'coins_tx')

        if not os.path.isdir(self.tx_dir):
            os.mkdir(self.tx_dir)

        self.tx_db_path = os.path.join(self.tx_dir, 'tx.sqlite')
        for table, info in seeds.items():
            if 'file' in info:
                info['file'] = info['file'].replace('${tx_dir}', self.tx_dir)

        self.db = DB('sqlite', self.tx_db_path, tables, seeds)
        LOGGER.info(f'{self.name} DB successfully initialized.')

    def _set_bot_thread(self):
        self.botThread = None
        children = self.baseplate._actor.children

        if children:
            slack = [a._actor for a in children if isinstance(a._actor, Slack)]
            if slack:
                self.botThread = slack[0].botThread

    def _set_defaults(self, kwargs):
        defaults = copy(DEFAULTS)
        defaults.update(kwargs.get('defaults', {}))

        for key, value in defaults.items():
            setattr(self, key, kwargs.get(key, value))

    # Action Methods
    def _get_balance(self, user, write_starting_balance=False, default=None):
        if default is None:
            default = 0

        balance = self.db.balance.get(user, return_field_value='balance')

        if not isinstance(balance, int) and write_starting_balance is True:
            balance = self.starting_value
            self._update_balance(user, balance)
            self._write_tx('SYSTEM', user, balance, 'Starting Balance')

        if not isinstance(balance, int):
            balance = default

        return balance

    def _get_balances(self):
        return self.db.balance.query(sort='balance,asc')

    def _get_user_name(self, user_id):
        if hasattr(self, 'botThread'):
            return self.botThread.get_user_name_by_id(user_id, True)

        return user_id

    def _pay(self, payer, payee, amount, memo=None):
        payer_balance = self._get_balance(payer)
        if amount > payer_balance:
            return 'NSF'

        payee_balance = self._get_balance(payee)
        payer_balance -= amount
        payee_balance += amount

        debit = self._update_balance(payer, payer_balance)
        credit = self._update_balance(payee, payee_balance)
        tx = self._write_tx(payer, payee, amount, memo)

        return all((debit, credit, tx))

    def _update_balance(self, user, amount):
        return self.db.balance.upsert({'user': user, 'balance': amount})

    def _write_tx(self, source, dest, amount, memo, ts=None):
        data = {
            'payer_id': source,
            'payee_id': dest,
            'amount': amount,
            'memo': memo,
            'tx_timestamp': ts if ts else utils.now()
        }

        return self.db.transaction.upsert(data)

    # Format Methods
    def _format_get_balance(self, user):
        balance = self._get_balance(user, True)
        if not isinstance(balance, int):
            return 'There was an error processing this request. See logs.'

        _user = f'<@{user}>' if user != 'pool' else 'The Pool'

        return f'{_user} has {balance} {self.name}.'

    # Helper Methods
    def _is_private_message(self, message):
        if not isinstance(message, dict):
            return False

        return utils.jsearch('metadata.is_private_message', message) is True
