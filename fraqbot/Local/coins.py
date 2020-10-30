import json
import logging
import os

from Legobot.Lego import Lego


LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
logger = logging.getLogger(__name__)


class Coins(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self.name = kwargs.get('name', 'Coins')
        self.starting_value = kwargs.get('starting_value', 20)
        self.trigger = kwargs.get('trigger', '!coins')
        self.balance_path = os.path.join(LOCAL_DIR, 'balances.json')
        self._load_balances()

    def listening_for(self, message):
        text = message.get('text')
        return isinstance(text, str) and text.startswith(self.trigger)

    def handle(self, message):
        response = None
        params = message['text'].split(' ')
        if len(params) > 1:
            user_id = message.get('metadata', {}).get('source_user')
            display_name = message.get('metadata', {}).get('display_name')

            if params[1] == 'balance':
                response = self._format_balance(user_id, display_name)
            elif params[1] in ['tip', 'pay'] and len(params) >= 4:
                try:
                    payee = params[2]
                    amount = int(params[3])
                    memo = ' '.join(params[4:]) if len(params) > 4 else None
                    response = self._pay(user_id, payee, amount, memo)
                except Exception as e:
                    logger.error(e)
                    response = None

        if response:
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

    def get_name(self):
        return self.name

    def get_help(self):
        lines = [f'Pay each other in {self.name}']
        lines.append(f'To see your balance: `{self.trigger} balance`')
        lines.append(f'To give coins: `{self.trigger} tip|pay < @person > '
                     '<int> [<optional memo>]`')
        return '\n'.join(lines)

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

            balance = self.balances[user_id]

        return balance

    def _format_balance(self, user_id, display_name):
        balance = self._get_balance(user_id)
        return '@{} has {} {}'.format(
            display_name, balance, self.name)

    def _pay(user_id, payee, amount, memo=None):
        logging.debug(self.__dict__)
