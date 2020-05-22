import logging
import re

from Legobot.Lego import Lego

from .helpers import call_rest_api


logger = logging.getLogger(__name__)


class SlumberClack(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self.config = kwargs.get('config', {})
        self.listeners = self.config.get('listeners', {})
        self._compile_listeners()
        self.base_url = self.config.get('clackApi', '')
        self.approvers = self.config.get('approvers', [])
        self.token = self.config.get('token', '')
        self.self = self.config.get('self', '')
        self.meta_conditions = self.config.get('metaConditions', {})
        self.matches = []

    def _compile_listeners(self):
        for k, v in self.listeners.items():
            if v.get('insensitive') is True:
                v['r'] = re.compile(v.get('r', r''), re.I)
            else:
                v['r'] = re.compile(v.get('r', r''))

    def listening_for(self, message):
        if message.get('metadata', {}).get('source_user', '') == self.self:
            return False

        if self.meta_conditions and self._check_meta(message):
            return False

        if not isinstance(message.get('text'), str):
            return False

        source_user = message.get('metadata', {}).get('source_user')
        ts = message.get('metadata', {}).get('ts')
        if message['text'].startswith('!suggestions'):
            self.matches.append(('suggestions', message['text']))
            return True
        elif message['text'].startswith('!suggest'):
            self.matches.append(('suggest', message['text'], source_user, ts))
            return True
        elif message['text'].startswith('!approve'):
            self.matches.append(('approve', message['text'], source_user))
            return True
        elif message['text'].startswith('!reject'):
            self.matches.append(('reject', message['text'], source_user))
            return True
        else:
            for k, v in self.listeners.items():
                if message['text'].startswith('!' + k):
                    self.matches.append((k, message['text'], source_user))
                    return True

                match = re.search(v['r'], message['text'])
                if match:
                    self.matches.append((
                        'match',
                        v.get('path', ''),
                        match[0].strip(),
                        source_user,
                        ts
                    ))

        return self.matches

    def handle(self, message):
        responses = []
        ops = {
            'suggestions': self._handle_suggestions,
            'suggest': self._handle_suggest,
            'approve': self._handle_approve,
            'reject': self._handle_reject,
            'match': self._handle_matches
        }
        for k in self.listeners.keys():
            ops[k] = self._handle_items
        while self.matches:
            match = self.matches.pop()
            op = match[0]
            if op in ops:
                responses.append(ops[op](match))

        for response in responses:
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

    def _check_meta(self, message):
        for k, v in self.meta_conditions.items():
            test = message.get('metadata', {}).get(k)
            if test:
                for op, value in v.items():
                    conditions = {
                        'eq': test == value if value else False,
                        'ne': test != value if value else True,
                        'in': test in value,
                        'not_in': test not in value
                    }
                    if conditions[op]:
                        return True

        return False

    def _notify(self, text, extra_users=None):
        url = 'https://slack.com/api/chat.postMessage'
        params = {
            'token': self.token,
            'text': text,
            'as_user': True
        }
        for user in self.approvers:
            params['channel'] = user
            call_rest_api(__name__, 'get', url, params=params)

    def _handle_suggestions(self, match):
        splt = match[1].split(' ')
        if len(splt) < 2 or splt[1] not in self.listeners:
            return 'Please provide a valid suggestions command.'
        else:
            url = self.base_url + '/' + splt[1] + '/suggestions'
            resp = call_rest_api(__name__, 'get', url, response='json')
            return '```{}```'.format('\n'.join(sorted(resp)))

    def _handle_suggest(self, match):
        splt = match[1].split(' ')
        if len(splt) < 3 or splt[1] not in self.listeners:
            return 'Please provide a valid suggestion.'
        else:
            return self._suggest(splt[1], splt[2], match[2], match[3])

    def _suggest(self, path, term, user, ts=None):
        url = '/'.join([self.base_url, path, 'suggest'])
        response = call_rest_api(__name__, 'get', url,
                                 params={'term': term, 'user': user, 'ts': ts},
                                 response='json')
        msg = response.get('message', '')
        if not response.get('status'):
            logger.error(f'Bad Suggestion: {msg}')
        else:
            msg = f'New suggestion from <@{user}>:\n`{term}`'
            self._notify(msg)

        return msg

    def _handle_approve(self, match):
        if match[2] not in self.approvers:
            return 'You are not authorized for approvals.'

        splt = match[1].split(' ')
        if len(splt) < 3 or splt[1] not in self.listeners:
            return 'Please provide a valid approval.'
        else:
            return self._approve(splt[1], splt[2], match[2])

    def _handle_reject(self, match):
        if match[2] not in self.approvers:
            return 'You are not authorized for approvals.'

        splt = match[1].split(' ')
        if len(splt) < 3 or splt[1] not in self.listeners:
            return 'Please provide a valid approval.'
        else:
            return self._reject(splt[1], splt[2], match[2])

    def _approve(self, path, term, approver):
        url = '/'.join([self.base_url, path, 'approve'])
        response = call_rest_api(__name__, 'get', url, params={'term': term},
                                 response='json')
        msg = response.get('message', '')
        if not response.get('status'):
            logger.error(f'Bad Approval: {msg}')
        else:
            self._notify(
                f'`{term}` approved by <@{approver}>.',
                extra_users=response.get('user')
            )

        return None

    def _reject(self, path, term, approver):
        url = '/'.join([self.base_url, path, 'reject'])
        response = call_rest_api(__name__, 'get', url, params={'term': term},
                                 response='json')
        msg = response.get('message', '')
        if not response.get('status'):
            logger.error(f'Bad Rejection: {msg}')
        else:
            self._notify(
                f'`{term}` rejected by <@{approver}>.',
                extra_users=response.get('user')
            )

    def _get_single(self, op):
        url = '/'.join([self.base_url, op])
        response = call_rest_api(__name__, 'get', url, response='json')
        return response

    def _get_all(self, op):
        url = '/'.join([self.base_url, op, 'all'])
        response = call_rest_api(__name__, 'get', url, response='json')
        if response:
            response = '```{}```'.format('\n'.join(sorted(response)))

        return response

    def _handle_items(self, match):
        op = match[0]
        text = match[1]
        if len(text.split(' ')) == 1:
            response = self._get_single(op)
        elif text.split(' ')[1] == 'all':
            response = self._get_all(op)
        else:
            response = f'Invalid request: `{text}`.'

        return response

    def _handle_matches(self, match):
        response = self._get_single(match[1])
        self._suggest(match[1], match[2], match[3], match[4])

        return response

    def get_name(self):
        return 'Clacks'

    def get_help(self, **kwargs):
        lines = [
            ('A system for keeping up with our beloved SimpleCast and '
             'HyperGiant.'),
            ('Come up with your best iteration and I\'ll add it to the list '
             'for approval. To invoke directly: ')
        ]

        for name, info in self.listeners.items():
            solo = name[:-1] if name.endswith('s') else name
            lines.append(f'\n- Get a {solo}: `!{name}`')
            lines.append(f'- Get all {name}: `!{name} all`')
            lines.append(f'- Suggest a {solo}: `!suggest {name} <suggestion>`')
            lines.append((f'- See all {solo} suggestions: '
                          f'`!suggetsions {name}`'))
            lines.append(f'- Approve a {solo}: `!approve {name} <suggestion>`')
            lines.append(f'- Reject a {solo}: `!reject {name} <suggestion>`')

        approvers = ', '.join([f'<@{a}>' for a in self.approvers])
        lines.append(f'Current approvers: {approvers}')

        return '\n'.join(lines)
