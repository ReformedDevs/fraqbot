from copy import copy
import json
import logging
import os
import re
import time

from Legobot.Connectors.Slack import Slack
from Legobot.Lego import Lego


LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
logger = logging.getLogger(__name__)


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

    def listening_for(self, message):
        text = message.get('text')
        return isinstance(text, str) and any(
            [text.startswith(t) for t in self.triggers])

    def handle(self, message):
        response = None
        params = message.get('metadata', {}).get('text').split(' ')
        user_id = message.get('metadata', {}).get('source_user')
        if len(params) > 1:
            display_name = message.get('metadata', {}).get('display_name')

            if params[1].lower() == 'help':
                response = self.get_help()
            elif params[1].lower() == 'balance':
                response = self._format_balance(user_id)
            elif params[1].lower() == 'balances' and user_id in self.admins:
                response = self._get_all_balances()
            elif params[1].lower() in ['tip', 'pay'] and len(params) >= 4:
                response = self._process_payment(
                    user_id, display_name, params[2:])

        if response:
            self._write_history(message, response)
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

    def get_name(self):
        return self.name

    def get_help(self):
        lines = [f'Pay each other in {self.name}']
        triggers = '|'.join(self.triggers)
        lines.append(f'To see your balance: `{triggers} balance`')
        lines.append(f'To give coins: `{triggers} tip|pay <user> '
                     '<int> [<optional memo>]`')
        return '\n'.join(lines)

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

    def _get_all_balances(self):
        bal = copy(self.balances)
        name_map = {k: f'@{self._get_user_name(k)}' for k in bal.keys()}
        max_key = max([4] + [len(name_map[k]) for k in bal.keys()])
        max_val = max([7] + [len(str(v)) for v in bal.values()])
        lines = []
        line = ''
        while len(line) < max_key + max_val + 7:
            line += '-'

        lines.append(line)

        for key in ['Name'] + sorted(bal.keys(), key=lambda k: name_map[k]):
            if key == 'Name':
                l_key = ' Name'
                val = 'Balance'
            else:
                l_key = ' {}'.format(name_map[key])
                val = bal[key]

            while len(l_key) < max_key + 2:
                l_key += ' '

            if key != 'Name':
                l_key = re.sub(r'@.*[^\s](?=\s*$)', f'<@{key}>', l_key)

            val = f' {val}'
            while len(val) < max_val + 2:
                val += ' '

            lines.append(f'|{l_key}|{val}|')
            if key == 'Name':
                lines.append(lines[0])

        lines.append(lines[0])

        return '```{}```'.format('\n'.join(lines))

    def _format_balance(self, user_id):
        balance = self._get_balance(user_id)
        return '<@{}> has {} {}'.format(
            user_id, balance, self.name)

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
