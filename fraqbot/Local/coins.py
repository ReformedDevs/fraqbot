from copy import copy
import json
import logging
import os
from random import choice
from random import randint
import re
import sys
import time

from tabulate import tabulate

from Legobot.Connectors.Slack import Slack
from Legobot.Lego import Lego


LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
logger = logging.getLogger(__name__)
CHOICES = [False, True, False, True]

sys.path.append(LOCAL_DIR)

import helpers as h  # noqa E402


class Coins(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        children = self.baseplate._actor.children
        if children:
            slack = [a._actor for a in children if isinstance(a._actor, Slack)]
            if slack:
                self.botThread = slack[0].botThread

        self.name = kwargs.get('name', 'Coins')
        self.admins = kwargs.get('admins', [])
        self.starting_value = kwargs.get('starting_value', 20)
        self.triggers = kwargs.get('triggers', ['!coins'])
        self.tx_path = os.path.join(LOCAL_DIR, 'coins_tx', 'tx.csv')
        self.history_path = os.path.join(LOCAL_DIR, 'coins_tx', 'history.log')
        self._init_tx_file()
        self.balance_path = os.path.join(
            LOCAL_DIR, 'coins_tx', 'balances.json')
        self._load_balances()
        self.next_pool = 0
        self._update_pool()
        self.pool_excludes = kwargs.get('pool_excludes', [])
        self.moiners = []
        self.moined = []

    def listening_for(self, message):
        _handle = False
        text = message.get('text')
        if isinstance(text, str):
            self._check_pool_ts(message)
            if any([text.startswith(t) for t in self.triggers]):
                _handle = True
            elif 'moin' in text.lower():
                moiner = message.get('metadata', {}).get('source_user')
                if (
                    moiner
                    and moiner not in self.moined
                    and moiner not in self.pool_excludes
                ):
                    self.moiners.append(moiner)
                    _handle = True

        return _handle

    def handle(self, message):
        if self.moiners:
            while self.moiners:
                moiner = self.moiners.pop(0)
                self._process_moin(moiner, message)
        else:
            response = None
            params = message.get('metadata', {}).get('text').split(' ')
            user_id = message.get('metadata', {}).get('source_user')
            if len(params) > 1:
                display_name = message.get('metadata', {}).get('display_name')

                if params[1].lower() == 'help':
                    response = self.get_help()
                elif params[1].lower() == 'pool':
                    response = self._format_balance('pool')
                    response += f'\nNext fill up in: {self._next_fill_up()}'
                elif params[1].lower() == 'balance':
                    response = self._format_balance(user_id)
                elif (
                    params[1].lower() == 'balances'
                    and user_id in self.admins
                ):
                    data = self._get_all_balances_data()
                    response = self._format_balances_table(
                        data[0], data[1]
                    )
                elif params[1].lower() in ['tip', 'pay'] and len(params) >= 4:
                    response = self._process_payment(
                        user_id, display_name, params[2:])

            if response:
                response = response.replace('<@pool>', 'The Pool')
                self._write_history(message, response)
                opts = self.build_reply_opts(message)
                self.reply(message, response, opts)

    def get_name(self):
        return self.name

    def get_help(self):
        lines = [f'Pay each other in {self.name}']
        triggers = '|'.join(self.triggers)
        lines.append(f'To see your balance and rank: `{triggers} balance`')
        lines.append(f'To give coins: `{triggers} tip|pay <user> '
                     '<int> [<optional memo>]`')
        lines.append(f'To see the pool balance: `{triggers} pool`')

        return '\n'.join(lines)

    def _process_moin(self, moiner, message):
        self.moined.append(moiner)
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
            pay = self._pay('pool', moiner, amt, 'Happy Moin!')
            if pay.get('ok'):
                msg = (f'<@{moiner}> received {amt} {self.name} from the '
                       'Pool. Happy Moin!')
                opts = self.build_reply_opts(message)
                self.reply(message, msg, opts)

    def _check_pool_ts(self, message):
        if not hasattr(self, 'update_pool_ts'):
            self._update_pool()
        else:
            msg_ts = float(message.get('metadata', {}).get('ts', 0))
            if msg_ts > self.next_pool:
                self._update_pool()

    def _update_pool(self):
        _now = h.now()
        if (
            not hasattr(self, 'update_pool_ts')
            or _now > self.next_pool
        ):
            self.update_pool_ts = _now
            self.next_pool = _now + (randint(8, 18) * 3600)
            amt = randint(25, 75) * 10
            pool_balance = self._get_balance('pool')
            self._update_balance('pool', pool_balance + amt)
            self._write_tx(None, 'pool', amt, 'daily pool deposit', _now)
            self.moined = []

    def _next_fill_up(self):
        out = []
        _now = h.now()
        diff = self.next_pool - _now
        hours = diff // 3600
        if hours:
            out.append(f'{hours} Hours')
        
        remain = diff % 3600
        minutes = remain // 60
        if minutes:
            out.append(f'{minutes} Minutes')

        return ', '.join(out)

    def _init_tx_file(self):
        if not os.path.isfile(self.tx_path):
            self._write_tx(
                'Payer', 'Payee', 'Amount', 'Memo', 'Timestamp', False)

    def _write_tx(self, payer, payee, amount, memo, ts=None, newline=True):
        if not ts:
            ts = time.time()

        line = f'{ts}|{payer}|{payee}|{amount}|{memo}'
        if newline is True:
            line = f'\n{line}'

        with open(self.tx_path, 'a') as f:
            f.write(line)

    def _write_history(self, message, response):
        line = json.dumps(
            {'message': message, 'response': response}, sort_keys=True) + '\n'

        with open(self.history_path, 'a') as f:
            f.write(line)

    def _load_balances(self):
        if not os.path.isfile(self.balance_path):
            self.balances = {}
            self._write_balances()
        else:
            with open(self.balance_path) as f:
                self.balances = json.load(f)

    def _write_balances(self):
        with open(self.balance_path, 'w') as f:
            json.dump(self.balances, f, indent=2, sort_keys=True)

    def _get_balance(self, user_id):
        balance = None
        if user_id:
            if user_id not in self.balances:
                self.balances[user_id] = self.starting_value
                self._write_balances()
                self._write_tx(
                    'SYSTEM', user_id, self.starting_value, 'Starting Balance')

            balance = self.balances[user_id]

        return balance

    def _get_user_name(self, user_id):
        out = user_id
        if hasattr(self, 'botThread'):
            out = self.botThread.get_user_name_by_id(user_id, True)

        return out

    def _get_all_balances_data(self):
        balances = []
        for uid, bal in self.balances.items():
            name = self._get_user_name(uid)
            if name:
                balances.append((uid, name, bal))

        table_data = [('Name', 'Balance')] + [
            ('@{}'.format(b[1]), b[2])
            for b in sorted(balances, key=lambda k: k[2])
        ]
        return [balances, table_data]

    def _format_balances_table(self, balances, table_data):
        out = tabulate(
            table_data,
            headers='firstrow',
            tablefmt='github'
        )
        for b in balances:
            out = out.replace('@{} '.format(b[1]), '<@{}> '.format(b[0]))
        
        return f'```{out}```'

    def _get_user_rank(self, user_id):
        table_data = self._get_all_balances_data()[1]
        rank = '?'
        user_name = self._get_user_name(user_id)
        for i, item in enumerate(table_data):
            if item[0] == user_name:
                rank = ('{}'.format(i))
        return rank

    def _format_balance(self, user_id):
        balance = self._get_balance(user_id)
        rank = self._get_user_rank(user_id)
        return '<@{}> has {} {} and is ranked # {}'.format(
            user_id, balance, self.name, rank)

    def _process_payment(self, payer, payer_display_name, params):
        payee = params[0]
        if not payee.startswith('@') and not payee.startswith('<@'):
            return f'{payee} is not a valid recipient.'

        try:
            amount = params[1]
            amt_msg = f'{amount} is not a valid amount: + integers only.'
            amount = int(amount)
            if amount <= 0:
                return amt_msg

        except Exception:
            return amt_msg

        memo = ' '.join(params[2:]) if len(params) > 2 else None
        paid = self._pay(payer, payee, amount, memo)

        if paid['ok'] is True:
            return (f'<@{payer}> successfully sent {amount} '
                    f'{self.name} to {payee}.')
        else:
            return paid.get('msg')

    def _pay(self, payer, payee, amount, memo=None):
        payee = payee.replace('<', '').replace('@', '').replace('>', '')
        out = {'ok': False}
        if payer == payee:
            out['msg'] = f'@{payer}, you can\'t pay yourself.'
            return out

        payer_balance = self._get_balance(payer)
        if payer_balance < amount:
            out['msg'] = f'You don\'t have enough {self.name}'
            return out

        payee_balance = self._get_balance(payee)

        try:
            self._update_balance(payer, payer_balance - amount)
            self._update_balance(payee, payee_balance + amount)
            self._write_tx(payer, payee, amount, memo)
            out['ok'] = True
        except Exception as e:
            out['msg'] = f'There was an error with the transaction: `{e}`'

        return out

    def _update_balance(self, user_id, balance):
        self.balances[user_id] = balance
        self._write_balances()
