import logging
import os
from random import choice
from random import randint
import re
import sys


LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(LOCAL_DIR)


from helpers.coins import CoinsBase  # noqa: E402
from helpers import file  # noqa: E402
from helpers import text  # noqa: E402
from helpers import utils  # noqa: E402


LOGGER = logging.getLogger(__name__)
CHOICES = (False, True, False, True, False)


class Coins(CoinsBase):
    # Std Methods
    def get_help(self):
        lines = [f'.\nPay each other in {self.name}:']
        triggers = '|'.join(self.triggers)
        lines.append(f'    • To see your balance: `{triggers} balance`')
        lines.append(f'    • To give coins: `{triggers} tip|pay <user> '
                     '<int> [<optional memo>]`')
        lines.append(f'    • To see when the pool resets: `{triggers} pool`')
        lines.append('\n    • *Admin functions:*')
        lines.append(f'        • To see all balances: `{triggers} balances`')
        lines.append(
            f'        • To see current escrow (DM only): `{triggers} escrow`')

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

        utils.set_properties(self, kwargs.get('properties', []), __file__)
        self._init_escrow()
        self.next_pool = self._get_next_pool()
        self._set_secret_word()
        self._update_pool()

    # Init Methods
    def _init_escrow(self):
        balance = self._get_balance('escrow', default=False)
        if balance is False:
            self._update_balance('escrow', 0)

    # Std Methods
    def listening_for(self, message):
        if utils.now() > getattr(self, 'next_pool', 0):
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

        # balance = self._get_balance('pool')
        # if not isinstance(balance, int):
        #     return msg

        til_next = self._get_time_to_next_fill_up()
        if not til_next:
            return msg

        return (f'Next fill up and disbursement in {til_next}')

    # Action Methods
    def _generate_secret_word(self, periods=None):
        if not periods or periods < 1:
            periods = 1

        fillups = self.db.pool_history.query(limit=periods + 1, sort='id,desc')
        fillups = (
            fillups[periods]['fillup_ts'],
            fillups[1]['next_fillup_ts']
        )

        users = self.db.balance.query(
            limit=10,
            sort='balance,asc',
            fields='user',
            _filter={'user__op': {
                'startswith': 'U', 'notin_': self.pool_excludes}}
        )
        users = utils.jsearch('[].user', users)
        messages = []

        for channel in self.secret_word_channels:
            messages += utils.call_slack_api(
                self.botThread.slack_client,
                'conversations.history',
                True,
                'messages',
                total_limit=10000,
                limit=1000,
                latest=fillups[1],
                oldest=fillups[0],
                channel=channel
            )

        user_search = ('[?contains([{}], user) '
                       '&& !contains(lower(text), `moin`) '
                       '&& !starts_with(text, `!ak`)]').format(
            ', '.join([f'`{u}`' for u in users])
        )
        messages = utils.jsearch(user_search, messages)
        word_pool = {}

        for message in messages:
            user = message['user']
            if user not in word_pool:
                word_pool[user] = []

            word_pool[user] += re.findall(r':[a-zA-Z0-9_-]+:', message['text'])
            string = re.sub(
                r'(:[a-zA-Z0-9_-]+:)|(<@U[A-Z0-9]+>)', '', message['text'])
            words = re.findall(r'\b\w+\b', string)
            word_pool[user] += [
                w.lower() for w in words
                if len(w) > 3
                and w.lower() not in self.common_words
            ]

        users = [k for k in word_pool.keys() if word_pool[k]]
        if len(users) > 2:
            user = choice(users)
            word = choice(word_pool[user])
        else:
            word, user = self._generate_secret_word(periods + 1)

        return word, user

    def _get_next_pool(self):
        next_pool = self.db.pool_history.query(
            limit=1, sort='id,desc', return_field_value='next_fillup_ts')

        return next_pool if next_pool else 0

    def _get_time_to_next_fill_up(self):
        out = []
        _now = utils.now()
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

    def _set_secret_word(self):
        pool_id = self.db.pool_history.query(
            limit=1, sort='id,desc', return_field_value='id')
        pool_id = pool_id if pool_id else 1
        record = self.db.secret_word.query(limit=1, _filter={'id': pool_id})

        if record:
            self.secret_word = record['secret_word']
        else:
            word, user = self._generate_secret_word()
            self.db.secret_word.upsert({
                'id': pool_id,
                'ts': utils.now(),
                'secret_word': word,
                'source_user': user
            })
            self.secret_word = word

    def _update_pool(self):
        _now = utils.now()
        if self.next_pool <= _now:
            self.next_pool = _now + (randint(4, 15) * 3600)
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

            self._set_secret_word()


class CoinsMiner(CoinsBase):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, **kwargs)

        self.moined = self._load('moined')
        self.sw_mined = self._load('sw_mined')
        self.next_pool = self._get_next_pool()
        self.pool_id = self._get_escrow_pool_id()
        self.secret_word = self._get_secret_word()

    # Std Methods
    def listening_for(self, message):
        if utils.now() > self.next_pool:
            self._reset(message)

        if not self.secret_word and utils.now() - self.gsw_ts > 120:
            self.secret_word = self._get_secret_word()

        _handle = False
        text = message.get('text')
        user = message.get('metadata', {}).get('source_user')
        channel = message.get('metadata', {}).get('source_channel')

        if (
            isinstance(text, str)
            and user
            and user not in self.pool_excludes
            and channel
        ):
            _handle = (
                ('moin' in text.lower() and user not in self.moined)
                or (self.secret_word in text.lower()
                    and user not in self.sw_mined
                    and channel in self.secret_word_channels)
            )

        return _handle

    # Handler Methods
    def handle(self, message):
        miner = message['metadata']['source_user']
        if 'moin' in message['text'].lower():
            self._mine(miner, 'moined')

        if self.secret_word in message['text'].lower():
            self._mine(miner, 'sw_mined')

    def _format_disburse(self, payment):
        response = None
        miner = payment['payee_id']
        amount = payment['amount']

        if payment['memo'].startswith('Moin'):
            memo = 'Happy Moin!'
            _type = 'Moin'
        elif payment['memo'].startswith('Secret Word'):
            memo = 'You guessed the secret word!'
            _type = 'Secret Word'
        else:
            memo = ''
            _type = ''

        paid = self._pay('escrow', miner, amount, memo)
        if paid:
            response = (f'- <@{miner}> received {amount} {self.name} from '
                        f'the Pool for {_type}.')

        return response

    # Action Methods
    def _disburse_from_escrow(self, message, escrow_group_id, secret_word):
        payments = self.db.escrow.query(
            _filter={'escrow_group_id': escrow_group_id}, sort='id,asc')
        responses = []

        for payment in payments:
            response = self._format_disburse(payment)
            if response:
                responses.append(response)

        if responses:
            msg = ('*{} Mining Report*\n'
                   'During the last pool period:```{}```\n'
                   'The Secret word was `{}`.\n\n'
                   'Happy Mining!').format(
                self.name, '\n'.join(responses), secret_word)

            for channel in self.disbursement_channels:
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

    def _get_secret_word(self):
        word = self.db.secret_word.get(
            self.pool_id, return_field_value='secret_word')
        self.gsw_ts = utils.now()

        return word

    def _load(self, prop):
        path = os.path.join(self.tx_dir, f'{prop}.json')
        if os.path.isfile(path):
            return file.load_file(path)

        return []

    def _load_moined(self):
        path = os.path.join(self.tx_dir, 'moined.json')
        if os.path.isfile(path):
            return file.load_file(path)

        return []

    def _mine(self, miner, prop):
        mined = getattr(self, prop)
        if miner not in mined:
            mined.append(miner)
            setattr(self, prop, mined)
            self._write(prop)

            if prop == 'moined' and not choice(CHOICES):
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
                self._to_escrow(miner, amt, prop)

        return None

    def _reset(self, message):
        self.next_pool = self._get_next_pool()
        self._disburse_from_escrow(message, self.pool_id, self.secret_word)
        self.pool_id = self._get_escrow_pool_id()
        self.secret_word = self._get_secret_word()
        self.moined = []
        self._write('moined')
        self.sw_mined = []
        self._write('sw_mined')

    def _to_escrow(self, miner, amt, prop):
        m_type = 'Secret Word' if prop == 'sw_mined' else 'Moin'
        tx_msg = (f'{m_type} Mining for {miner}. '
                  f'Escrow group id: {self.pool_id}')

        if self._pay('pool', 'escrow', amt, tx_msg):
            self.db.escrow.upsert({
                'escrow_group_id': self.pool_id,
                'tx_timestamp': utils.now(),
                'payer_id': 'pool',
                'payee_id': miner,
                'amount': amt,
                'memo': tx_msg
            })

    def _write(self, prop):
        path = os.path.join(self.tx_dir, f'{prop}.json')
        file.write_file(path, getattr(self, prop), 'json')


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
        return self._format_get_balances()

    def _handle_escrow(self, message, params):
        private = message.get('metadata', {}).get('is_private_message', False)
        if private:
            current_escrow_id = self.db.pool_history.query(
                sort={'field': 'id', 'direction': 'desc'},
                limit=1,
                return_field_value='id'
            )
            if current_escrow_id:
                return self._format_get_escrow(current_escrow_id)

    # Formatter Methods
    def _format_get_balances(self):
        response = None
        balances = self._get_balances()
        balances = utils.jsearch('[?starts_with(user, `"U"`)]', balances)
        if balances:
            response = text.tabulate_data(
                balances,
                {'user': 'User', 'balance': 'Balance'},
                fields=['user', 'balance'],
                user_id_field='user',
                thread=self.botThread
            )

        return response

    def _format_get_escrow(self, escrow_group_id):
        response = None
        escrow = self.db.escrow.query(
            fields=['payee_id', 'amount', 'memo'],
            _filter={'escrow_group_id': escrow_group_id},
            sort={'field': 'tx_timestamp', 'order': 'asc'}
        )

        if escrow:
            escrow = utils.jsearch(
                ('[].{payee_id: payee_id, amount: amount, memo: split_items'
                 '(memo, `Mining`, `1`)}'),
                escrow
            )
            table = text.tabulate_data(
                escrow,
                {'payee_id': 'User', 'amount': 'Amount', 'memo': 'Memo'},
                fields=['payee_id', 'amount', 'memo'],
                user_id_field='payee_id',
                thread=self.botThread
            )
            response = f'Current Unpaid Escrow: {table}'

        return response
