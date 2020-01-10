import logging

from Legobot.Lego import Lego
import re
from slackclient import SlackClient

logger = logging.getLogger(__name__)


class Dictator(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock)
        self.token = kwargs.get('token', '')
        self.conditions = [
            {
                'type': 'regex',
                'text': r'(<!channel>)|(@channel)',
                'user_exceptions': [
                    'U1YMD6Z4L',  # specs
                    'U0H0F95TJ',  # chuck
                    'U1ZB3CFV3'  # jeff
                ]
            },
            {
                'type': 'match',
                'text': 'woke'
            }
        ]

    def listening_for(self, message):
        if (message.get('text')
                and message['metadata'].get('subtype') != 'message_deleted'):
            try:
                return self._check_conditions(message)
            except Exception as e:
                logger.error(('Dictator lego failed to check the message text:'
                             ' {}').format(e))
                return False

    @staticmethod
    def _check_regex(message, check):
        check = re.compile(check, re.IGNORECASE)
        matches = re.search(check, message.replace('`', ''))
        return matches

    @staticmethod
    def _check_match(message, check):
        return check in message

    def _check_conditions(self, message):
        types = {
            'match': self._check_match,
            'regex': self._check_regex
        }
        for condition in self.conditions:
            if (message['metadata'].get('source_user')
                    not in condition.get('user_exceptions', [])):
                test = types[condition.get('type', self._check_match)](
                    message['text'], condition.get('text'))
                if test:
                    return True

        return False

    def handle(self, message):
        c = SlackClient(token=self.token)

        channel = message['metadata'].get('source_channel')
        ts = message['metadata'].get(
            'ts', message['metadata'].get('thread_ts'))

        if channel and ts:
            c.api_call('chat.delete', channel=channel, ts=ts)
