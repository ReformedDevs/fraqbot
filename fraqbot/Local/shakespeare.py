import logging
import os
import random
import sys

from Legobot.Lego import Lego


logger = logging.getLogger(__name__)
LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))

if LOCAL_DIR not in sys.path:
    sys.path.append(LOCAL_DIR)


import helpers as h  # noqa E402


class Shakespeare(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self.insult_array = []
        insults = h.load_file(
            os.path.join(LOCAL_DIR, 'lists', 'quotes.txt'), raw=True)

        if insults:
            self.insult_array = insults.splitlines()

    def listening_for(self, message):
        text = message.get('text')

        return isinstance(text, str) and text.startswith('!shake')

    def _get_quote(self, word):
        default = 'Not so much brain as ear wax.'

        if not word:
            return default

        short_list = [phrase for phrase in self.insult_array if word in phrase]

        if not short_list:
            return default

        return random.choice(short_list)

    def handle(self, message):
        logger.debug('Handling Shake request: {}'.format(message['text']))
        word = message['text'][6:].strip()

        insult = self._get_quote(word)
        opts = self.build_reply_opts(message)
        self.reply(message, insult, opts)

    def get_name(self):
        return 'Shakespeare_Insults'

    def get_help(self):
        return 'Get a random Shakespeare insult. Usage: !shake <word>'
