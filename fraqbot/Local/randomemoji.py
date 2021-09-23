import logging
import os
import random
import sys

from Legobot.Connectors.Slack import Slack
from Legobot.Lego import Lego


logger = logging.getLogger(__name__)
LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))

if LOCAL_DIR not in sys.path:
    sys.path.append(LOCAL_DIR)


from helpers import utils  # noqa: E402


class RandomEmoji(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self._set_client()
        self.max_how_many = 20
        self.min_how_many = 1
        self.default_how_many = 5

    def listening_for(self, message):
        text = message.get('text')

        return isinstance(text, str) and text.startswith('!emoji')

    def _set_client(self):
        self.client = None
        children = self.baseplate._actor.children

        if children:
            slack = [a._actor for a in children if isinstance(a._actor, Slack)]
            if slack:
                self.client = slack[0].botThread.slack_client

    def _fetch_slack_emojis(self):
        return utils.call_slack_api(
                self.client,
                'emoji.list',
                False,
                'emoji'
            )

    def _get_emoji(self, how_many, search_term):
        how_many_limited = max(
            self.min_how_many,
            min(self.max_how_many, how_many)
        )
        search_term_normalized = (search_term
                                  if search_term
                                  and len(search_term) > 0
                                  else None)

        emoji_response = self._fetch_slack_emojis()

        emoji_list = list(emoji_response.keys())

        if (search_term_normalized):
            filtered_emoji_list = [
                emoji_name for emoji_name
                in emoji_list
                if search_term_normalized in emoji_name
            ]
            if len(filtered_emoji_list) < 1:
                return ('Nothing matched search term. '
                        + 'Please accept this instead: :'
                        + random.choice(emoji_list) + ':')
            else:
                emoji_list = filtered_emoji_list

        return (':'
                + ': :'.join(random.choices(
                        emoji_list, k=how_many_limited
                    )).strip()
                + ':')

    def handle(self, message):
        logger.debug(
            'Handling Random Emoji request: {}'.format(message['text'])
        )
        opts = self.build_reply_opts(message)

        all_additional_text = message['text'][6:]
        if all_additional_text.strip() == 'help':
            return self.reply(message, self.get_help(), opts)

        how_many = all_additional_text[0:3].strip()
        search_term = all_additional_text[3:].strip()

        if len(how_many) > 0 and not how_many.isdigit():
            return self.reply(
                message,
                '\'{}\' is not a valid integer.'.format(how_many),
                opts
            )

        how_many = (int(how_many)
                    if len(how_many) > 0
                    else self.default_how_many)

        random_emojis = self._get_emoji(how_many, search_term)
        self.reply(message, random_emojis, opts)

    def get_name(self):
        return 'Random_Emoji'

    def get_help(self):
        return ('Get a random Emoji (or multiple!). '
                + 'Search also available. Limit 20. '
                + 'Usage: !emoji <how_many[default=5]> '
                + '<search_term[optional]>')
