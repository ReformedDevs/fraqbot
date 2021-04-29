from Legobot.Lego import Lego
import logging
import os
import random
import sys

logger = logging.getLogger(__name__)


class Shakespeare(Lego):
    insult_array = []

    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))

        LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
        if LOCAL_DIR not in sys.path:
            sys.path.append(LOCAL_DIR)

        with open(os.path.join(LOCAL_DIR, 'lists/quotes.txt')) as my_file:
            for line in my_file:
                Shakespeare.insult_array.append(line)

    def listening_for(self, message):
        text = message.get('text')
        return isinstance(text, str) and text.startswith('!shake')

    def _get_quote(word, insult_array):
        shortList = [phrase for phrase in insult_array if word in phrase]
        if len(shortList) == 0:
            return("Not so much brain as ear wax.")
        return(random.choice(shortList))

    def handle(self, message):
        logger.debug('Handling Shake request: {}'.format(message['text']))
        word = message['text'].replace(message['text'].split()[0], '').strip()

        insult = self._get_quote(word, Shakespeare.insult_array)

        opts = self.build_reply_opts(message)
        self.reply(message, insult, opts)

    def get_name(self):
        return 'Shakespeare_Insults'

    def get_help(self):
        help_text = ('Get a random Shakespeare insult. '
                     'Usage: !shake <word>')
        return help_text
