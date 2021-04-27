from copy import copy
import logging
import os
from random import choice
from random import randint
import re
import sys

from tabulate import tabulate

from Legobot.Connectors.Slack import Slack
from Legobot.Lego import Lego


LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(LOCAL_DIR)

import helpers as h  # noqa: E402
from sql import DB  # noqa: E402


LOGGER = logging.getLogger(__name__)
CHOICES = (False, True, False, True, False)
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

        # set tx locations and load/initialize db
        tables = {}
        table_dir = os.path.join(LOCAL_DIR, 'tables')
        for _file in os.listdir(table_dir):
            path = os.path.join(table_dir, _file)
            if os.path.isfile(path):
                tables.update(h.load_file(path))

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
            'tx_timestamp': ts if ts else h.now()
        }

        return self.db.transaction.upsert(data)


class Coins(CoinsBase):
    # Std Methods
    def get_help(self):
        lines = [f'Pay each other in {self.name}']
        triggers = '|'.join(self.triggers)
        lines.append(f'To see your balance: `{triggers} balance`')
        lines.append(f'To give coins: `{triggers} tip|pay <user> '
                     '<int> [<optional memo>]`')
        lines.append(f'To see the pool balance: `{triggers} pool`')

        return '\n'.join(lines)

    def get_name(self):
        return self.name

    def listening_for(self, message):
        _handle = False
        text = message.get('text')
        if isinstance(text, str):
            _handle = any([text.startswith(t) for t in self.triggers])

        return _handle

    # Handle Methods
    def handle(self, message):
        response = None
        text = message.get('metadata', {}).get('text', '')
        params = re.split(r'\s+', text)
        params.pop(0)
        if params:
            cmd = params.pop(0)
            method = getattr(self, f'_handle_{cmd}', None)
            if method:
                response = method(message, params)

        if response:
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

    def _handle_balance(self, message, params):
        user = message['metadata']['source_user']
        return self._format_get_balance(user)

    def _handle_help(self, message, params):
        return self.get_help()

    def _handle_pay(self, message, params):
        payer = message['metadata']['source_user']
        if len(params) < 2:
            return 'Invalid tip action. Not enough parameters.'

        payee = params.pop(0)
        amount = params.pop(0)
        if params:
            memo = ' '.join(params)
        else:
            memo = None

        return self._format_pay(payer, payee, amount, memo)

    def _handle_tip(self, message, params):
        return self._handle_pay(message, params)

    # Format Methods
    def _format_get_balance(self, user):
        balance = self._get_balance(user, True)
        if not isinstance(balance, int):
            return 'There was an error processing this request. See logs.'

        return f'<@{user}> has {balance} {self.name}.'

    def _format_pay(self, payer, payee, amount, memo=None):
        if not payee.startswith('@') and not payee.startswith('<@'):
            return f'{payee} is not a valid tip recipient.'

        _payee = re.sub(r'[@<>]', '', payee)

        if payer == _payee:
            return f'You can\'t pay yourself. Everybody shame <@{payer}>!'

        msg = f'Invalid tip amount, {amount}. Positive integers only.'

        try:
            amount = int(amount)
            if amount <= 0:
                return msg
        except Exception:
            return msg

        paid = self._pay(payer, _payee, amount, memo)
        if not paid:
            return 'There was an error processing this request. See logs.'
        elif paid == 'NSF':
            return f'You do not have enough {self.name} for that <@{payer}>.'
        else:
            return (f'<@{payer}> successfully sent {amount} {self.name} '
                    f'to <@{_payee}>.')


class CoinsPoolManager(CoinsBase):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, **kwargs)

        self._init_escrow()
        self.next_pool = self._get_next_pool()
        self._update_pool()

    # Init Methods
    def _init_escrow(self):
        balance = self._get_balance('escrow', default=False)
        if balance is False:
            self._update_balance('escrow', 0)

    # Std Methods
    def listening_for(self, message):
        if h.now() > getattr(self, 'next_pool', 0):
            self._update_pool()

        _handle = False
        text = message.get('text')
        if isinstance(text, str):
            params = re.split(r'\s+', text.lower())
            if (
                len(params) > 1
                and params[0] in self.triggers
                and params[1] == 'pool'
            ):
                _handle = True

        return _handle

    # Hanlde Methods
    def handle(self, message):
        response = self._format_get_pool()
        if response:
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

    # Format Methods
    def _format_get_pool(self):
        msg = 'There was an error processing this request. See logs.'

        balance = self._get_balance('pool')
        if not isinstance(balance, int):
            return msg

        til_next = self._get_time_to_next_fill_up()
        if not til_next:
            return msg

        return (f'The Pool has {balance} {self.name}.\n'
                f'Next fill up in {til_next}')

    # Action Methods
    def _get_next_pool(self):
        next_pool = self.db.pool_history.query(
            limit=1, sort='id,desc', return_field_value='next_fillup_ts')

        return next_pool if next_pool else 0

    def _get_time_to_next_fill_up(self):
        out = []
        _now = h.now()
        diff = self.next_pool - _now
        if diff < 60:
            return f'{diff} Seconds'

        hours = diff // 3600
        if hours:
            out.append(f'{hours} Hours')

        remain = diff % 3600
        minutes = remain // 60
        if minutes:
            out.append(f'{minutes} Minutes')

        return ', '.join(out)

    def _update_pool(self):
        _now = h.now()
        if self.next_pool <= _now:
            self.next_pool = _now + (randint(8, 18) * 3600)
            amt = randint(25, 75) * 10
            pool_balance = self._get_balance('pool', True)

            if self._update_balance('pool', pool_balance + amt):
                if self._write_tx(
                        'None', 'pool', amt, 'daily pool deposit', _now):
                    self.db.pool_history.upsert({
                        'fillup_ts': _now,
                        'next_fillup_ts': self.next_pool,
                        'amount': amt
                    })


class CoinsMiner(CoinsBase):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, **kwargs)

        self.moined = self._load_moined()
        self.next_pool = self._get_next_pool()
        self.pool_id = self._get_escrow_pool_id()

    # Std Methods
    def listening_for(self, message):
        if h.now() > self.next_pool:
            self._reset(message)

        _handle = False
        text = message.get('text')
        user = message.get('metadata', {}).get('source_user')

        if (
            isinstance(text, str)
            and user
            and user not in self.moined
            and user not in self.pool_excludes
        ):
            _handle = 'moin' in text.lower()

        return _handle

    # Handler Methods
    def handle(self, message):
        moiner = message['metadata']['source_user']
        self._mine(moiner)

    def _format_disburse(self, payment):
        response = None
        moiner = payment['payee_id']
        amount = payment['amount']
        paid = self._pay(
            'escrow', moiner, amount, 'Happy Moin!')
        if paid:
            response = (f'- <@{moiner}> received {amount} {self.name} from '
                        'the Pool.')

        return response

    # Action Methods
    def _disburse_from_escrow(self, message, escrow_group_id):
        payments = self.db.escrow.query(
            _filter={'escrow_group_id': escrow_group_id}, sort='id,asc')
        responses = []

        for payment in payments:
            response = self._format_disburse(payment)
            if response:
                responses.append(response)

        if responses:
            msg = 'During the last pool period:```{}```\nHappy Moin!'.format(
                '\n'.join(responses))
            channel = self.botThread.get_channel_id_by_name('general')
            if channel:
                self.botThread.slack_client.api_call(
                    'chat.postMessage',
                    as_user=True,
                    channel=channel,
                    text=msg
                )

    def _get_escrow_pool_id(self):
        return self._get_last_pool_item('id', 1)

    def _get_last_pool_item(self, return_field=None, default=None):
        q_kwargs = {'limit': 1, 'sort': 'id,desc'}
        if return_field:
            q_kwargs['return_field_value'] = return_field

        data = self.db.pool_history.query(**q_kwargs)

        if data is None and return_field:
            data = default

        return data

    def _get_next_pool(self):
        return self._get_last_pool_item('next_fillup_ts', 0)

    def _load_moined(self):
        path = os.path.join(self.tx_dir, 'moined.json')
        if os.path.isfile(path):
            return h.load_file(path)

        return []

    def _mine(self, moiner):
        if moiner not in self.moined:
            self.moined.append(moiner)
            self._write_moined()
            if not choice(CHOICES):
                return None

            pool_balance = self._get_balance('pool')
            opts = []
            if pool_balance >= 14:
                opts.append(7)
            if pool_balance >= 22:
                opts.append(11)
            if pool_balance >= 26:
                opts.append(13)
            if pool_balance >= 34:
                opts.append(17)

            divvy = None
            if opts:
                divisor = choice(opts)
                divvy = pool_balance // divisor

            if opts and pool_balance and divvy:
                divvy = divvy // 2 + 1 if divvy >= 3 else 2
                amt = randint(2, divvy) * divisor
                self._to_escrow(moiner, amt)

        return None

    def _reset(self, message):
        self.next_pool = self._get_next_pool()
        self._disburse_from_escrow(message, self.pool_id)
        self.pool_id = self._get_escrow_pool_id()
        self.moined = []
        self._write_moined()

    def _to_escrow(self, moiner, amt):
        tx_msg = (f'Mining for {moiner}. Escrow group id: {self.pool_id}')
        if self._pay('pool', 'escrow', amt, tx_msg):
            self.db.escrow.upsert({
                'escrow_group_id': self.pool_id,
                'tx_timestamp': h.now(),
                'payer_id': 'pool',
                'payee_id': moiner,
                'amount': amt,
                'memo': tx_msg
            })

    def _write_moined(self):
        path = os.path.join(self.tx_dir, 'moined.json')
        h.write_file(path, self.moined, 'json')


class CoinsAdmin(CoinsBase):
    # Std Methods
    def listening_for(self, message):
        _handle = False
        user = message.get('metadata', {}).get('source_user')
        if user and user in self.admins:
            text = message.get('text')
            if isinstance(text, str):
                _handle = any([
                    text.lower().startswith(t)
                    for t in self.triggers
                ])

        return _handle

    # Handler Methods
    def handle(self, message):
        response = None
        text = message.get('metadata', {}).get('text', '')
        params = re.split(r'\s+', text)
        params.pop(0)
        if params:
            cmd = params.pop(0)
            method = getattr(self, f'_handle_{cmd}', None)
            if method:
                response = method(message, params)

        if response:
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

    def _handle_balances(self, message, params):
        user = message['metadata']['source_user']
        return self._format_get_balances(user)

    # Formatter Methods
    def _format_get_balances(self, user):
        response = None
        if user in self.admins:
            balances = self._get_balances()
            if balances:
                data = []
                for b in balances:
                    name = self._get_user_name(b['user'])
                    if name:
                        data.append((b['user'], name, b['balance']))

                response = tabulate(
                    [('Name', 'Balance')] + [
                        ('@{}'.format(d[1]), d[2]) for d in data],
                    headers='firstrow',
                    tablefmt='github'
                )

                for d in data:
                    response = response.replace(
                        '@{}'.format(d[1]), '<@{}>'.format(d[0]))

                response = f'```{response}```'

        return response
