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


from helpers.text import parse_message_params  # noqa E402
from helpers import utils  # noqa: E402


class RandomEmoji(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self._set_client()
        self.max_how_many = 20
        self.min_how_many = 1
        self.default_how_many = 5

    def listening_for(self, message):
        text = str(message.get('text', ''))
        msg_type = utils.jsearch('metadata.subtype', message)

        return msg_type is None and text.startswith('!emoji')

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
        search_term_normalized = (search_term.lower()
                                  if search_term
                                  and len(search_term) > 0
                                  else None)

        emoji_response = self._fetch_slack_emojis()

        emoji_list = list(emoji_response.keys())

        if search_term_normalized:
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

        chosen_emojis = []
        if len(emoji_list) > how_many:
            chosen_emojis = random.sample(emoji_list, k=how_many_limited)
        else:
            chosen_emojis = list(emoji_list)  # clone b/c shuffle is in place
            random.shuffle(chosen_emojis)
            how_many_more = how_many_limited - len(chosen_emojis)
            chosen_emojis.extend(random.choices(emoji_list, k=how_many_more))

        return (':'
                + ': :'.join(chosen_emojis)
                + ':')

    def handle(self, message):
        logger.debug(
            'Handling Random Emoji request: {}'.format(message['text'])
        )
        opts = self.build_reply_opts(message)

        all_additional_text = message['text'][6:]
        if all_additional_text.strip() == 'help':
            return self.reply(message, self.get_help(), opts)

        params = parse_message_params(
            message['text'],
            fields=['cmd', 'how_many', 'search_term']
        )
        how_many = params['how_many']

        if how_many and len(how_many) > 0 and not how_many.isdigit():
            return self.reply(
                message,
                '\'{}\' is not a valid integer.'.format(how_many),
                opts
            )

        how_many = (int(how_many)
                    if how_many and len(how_many) > 0
                    else self.default_how_many)

        random_emojis = self._get_emoji(how_many, params['search_term'])
        self.reply(message, random_emojis, opts)

    def get_name(self):
        return 'Random_Emoji'

    def get_help(self):
        return ('Get a random Emoji (or multiple!). '
                + 'Search also available. Limit 20. '
                + 'Usage: !emoji <how_many[default=5]> '
                + '<search_term[optional]>')
