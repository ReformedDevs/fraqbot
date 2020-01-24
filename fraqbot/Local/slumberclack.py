import json
import logging
import re

from Legobot.Lego import Lego
import requests


logger = logging.getLogger(__name__)


class SlumberClack(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock)
        self.config = kwargs.get('config', {})
        self.listeners = self.config.get('listeners', {})
        self.base_url = self.config.get('clackApi', '')
        self.approvers = self.config.get('approvers', [])
        self.token = self.config.get('token', '')
        self.meta_conditions = self.config.get('metaConditions', {})
        self.matches = []

    def listening_for(self, message):
        if self.meta_conditions and self._check_meta(message):
            return False

        if not isinstance(message.get('text'), str):
            return False

        source_user = message.get('metadata', {}).get('source_user')
        ts = message.get('metadata', {}).get('ts')
        if message['text'].startswith('!suggest'):
            self.matches.append(('suggest', message['text'], source_user, ts))
            return True
        elif message['text'].startswith('!approve'):
            self.matches.append(('approve', message['text'], source_user))
            return True
        else:
            for k, v in self.listeners.items():
                if message['text'].startswith('!' + k):
                    self.matches.append((k, message['text'], source_user))
                    return True

                match = re.search(re.compile(v.get('r', '')), message['text'])
                if match:
                    self.matches.append((
                        'match',
                        v.get('path', ''),
                        match[0],
                        source_user,
                        ts
                    ))

        return self.matches

    def handle(self, message):
        responses = []
        ops = {
            'suggest': self._handle_suggest,
            'approve': self._handle_approve,
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

    def _call_api(self, url, **kwargs):
        call = requests.get(url, **kwargs)
        if call.status_code == requests.codes.ok:
            return json.loads(call.text)
        else:
            msg = (f'An error ocurred calling {url}. '
                   f'{call.status_code}: {call.text}')
            logger.error(msg)
            return None

    def _notify(self, text):
        url = 'https://slack.com/api/chat.postMessage'
        params = {
            'token': self.token,
            'text': text,
            'as_user': True
        }
        for user in self.approvers:
            params['channel'] = user
            response = self._call_api(url, params=params)
            if not response.get('ok'):
                logger.error(f'Error notifying user {user}: {response}')

    def _handle_suggest(self, match):
        splt = match[1].split(' ')
        if len(splt) < 3 or splt[1] not in self.listeners:
            return 'Please provide a valid suggestion.'
        else:
            return self._suggest(splt[1], splt[2], match[2], match[3])

    def _suggest(self, path, term, user, ts=None):
        url = '/'.join([self.base_url, path, 'suggest'])
        response = self._call_api(
            url, params={'term': term, 'user': user, 'ts': ts})
        msg = response.get('message', '')
        if not response.get('status'):
            logger.error(f'Bad Suggestion: {msg}')
        else:
            self._notify(f'New suggestion: `{term}`')

        return msg

    def _handle_approve(self, match):
        if match[2] not in self.approvers:
            return 'You are not authorized for approvals.'

        splt = match[1].split(' ')
        if len(splt) < 3 or splt[1] not in self.listeners:
            return 'Please provide a valid approval.'
        else:
            return self._approve(splt[1], splt[2])

    def _approve(self, path, term):
        url = '/'.join([self.base_url, path, 'approve'])
        response = self._call_api(url, params={'term': term})
        msg = response.get('message', '')
        if not response.get('status'):
            logger.error(f'Bad Approval: {msg}')

        return msg

    def _get_single(self, op):
        url = '/'.join([self.base_url, op])
        response = self._call_api(url)
        return response

    def _get_all(self, op):
        url = '/'.join([self.base_url, op, 'all'])
        response = self._call_api(url)
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
