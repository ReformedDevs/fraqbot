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
        self.operation = None
        self.matches = []

    def listening_for(self, message):
        if not isinstance(message.get('text'), str):
            return False

        if message['text'].startswith('!suggest'):
            self.operation = 'suggest'
            return True
        elif message['text'].startswith('!approve'):
            self.operation = 'approve'
            return True
        else:
            for k, v in self.listeners.items():
                if message['text'].startswith('!' + k):
                    self.operation = k
                    return True

                match = re.search(re.compile(v.get('r', '')), message['text'])
                if match:
                    self.matches.append((v.get('path', ''), match[0]))

        return self.matches

    def handle(self, message):
        op = self.operation
        self.operation = None
        responses = []
        standard_ops = {
            'suggest': self._handle_suggest,
            'approve': self._handle_approve
        }
        if op in standard_ops:
            responses.append(standard_ops[op](message))
        elif op in self.listeners:
            responses.append(self._handle_items(op, message))
        elif self.matches:
            while self.matches:
                responses.append(self._handle_matches(self.matches.pop()))

        for response in responses:
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

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

    def _handle_suggest(self, message):
        splt = message['text'].split(' ')
        if len(splt) < 3 or splt[1] not in self.listeners:
            return 'Please provide a valid suggestion.'
        else:
            return self._suggest(splt[1], splt[2])

    def _suggest(self, path, term):
        url = '/'.join([self.base_url, path, 'suggest'])
        response = self._call_api(url, params={'term': term})
        msg = response.get('message', '')
        if not response.get('status'):
            logger.error(f'Bad Suggestion: {msg}')
        else:
            self._notify(f'New suggestion: `{term}`')

        return msg

    def _handle_approve(self, message):
        user = message.get('metadata', {}).get('source_user', '')
        if user not in self.approvers:
            return 'You are not authorized for approvals.'

        splt = message['text'].split(' ')
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
            response = '```{}```'.format('\n'.join(response))

        return response

    def _handle_items(self, op, message):
        text = message['text']
        if len(text.split(' ')) == 1:
            response = self._get_single(op)
        elif text.split(' ')[1] == 'all':
            response = self._get_all(op)
        else:
            response = f'Invalid request: `{text}`.'

        return response

    def _handle_matches(self, match):
        response = self._get_single(match[0])
        self._suggest(match[0], match[1])

        return response
