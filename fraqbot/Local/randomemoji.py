import logging
import os
import random
import sys

from Legobot.Lego import Lego


logger = logging.getLogger(__name__)
LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))

if LOCAL_DIR not in sys.path:
    sys.path.append(LOCAL_DIR)


from helpers import utils  # noqa: E402


class RandomEmoji(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))

    def listening_for(self, message):
        text = message.get('text')

        return isinstance(text, str) and text.startswith('!emoji')

    def _get_emoji(self, how_many):
        maximum_how_many = 20
        minimum_how_many = 1
        how_many_limited = max(minimum_how_many, min(maximum_how_many, how_many))
        
        emoji_response = utils.call_slack_api(
                self.slack_client,
                'emoji.list',
                True,
                'emoji',
                total_limit=10000,
                limit=1000,
            )
        
        final_emoji_text = ""

        x = range(int(how_many_limited))
        for n in x:
            final_emoji_text += ' :' + random.choice(list(emoji_response.items()))[0] + ':'

        return final_emoji_text

    def handle(self, message):
        logger.debug('Handling Random Emoji request: {}'.format(message['text']))
        default_how_many = 5
        how_many = int(message['text'][6:].strip() or default_how_many)

        random_emojis = self._get_emoji(how_many)
        opts = self.build_reply_opts(message)
        self.reply(message, random_emojis, opts)

    def get_name(self):
        return 'Random_Emoji'

    def get_help(self):
        return 'Get a random Emoji (or multiple!). Usage: !emoji <how_many[default=5]>'
