import html
import logging
import os
import random
import re
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
        self.max_emoji_talk_emojis = 50
        self.number_to_emoji_map = {
            '0': ':zero:',
            '1': ':one:',
            '2': ':two:',
            '3': ':three:',
            '4': ':four:',
            '5': ':five:',
            '6': ':six:',
            '7': ':seven:',
            '8': ':eight:',
            '9': ':nine:',
            ' ': ':blank:',
            '!': ':exclamation:',
            '?': ':question:',
            '"': ':air_quotes:',
        }

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

    def _get_emoji(self, how_many, search_term, use_find_feature=False):
        search_term = search_term.lower() if search_term else None
        how_many_limited = max(
            self.min_how_many,
            min(self.max_how_many, how_many)
        )
        all_emoji = self._fetch_slack_emojis()

        if not all_emoji:
            return None

        if search_term:
            emoji = [e for e in all_emoji.keys() if search_term in e]

            if not emoji:
                return ('Nothing matched search term. Please accept this '
                        f'instead: :{random.choice(list(all_emoji.keys()))}:')
        else:
            emoji = list(all_emoji.keys())

        if len(emoji) > how_many_limited:
            chosen_emoji = random.sample(emoji, k=how_many_limited)
        else:
            chosen_emoji = list(emoji)  # clone b/c shuffle is in place
            random.shuffle(chosen_emoji)
            additional = 0

            if not use_find_feature:
                additional = how_many_limited - len(chosen_emoji)

            chosen_emoji.extend(random.choices(emoji, k=additional))

        return f':{": :".join(chosen_emoji)}:'

    def _char_to_emoji(self, char):
        char_lower = char.lower()
        if char_lower in self.number_to_emoji_map:
            return self.number_to_emoji_map[char_lower]
        elif re.match(r'[a-zA-Z]', char_lower):
            return f':{char_lower}:'
        else:
            return char

    def _get_emoji_talk(self, text):
        regex = re.compile(r'(?::[a-zA-Z0-9_-]+:)'
                           r'|(?:<[@#][A-Z0-9]{8,12}(?:\|[a-z_-]+)?>)'
                           r'|%%')
        emj_tgs_and_plchldrs = re.findall(regex, text)
        text = re.sub(regex, '%%', text)
        emoji_count = len([
            e for e in emj_tgs_and_plchldrs
            if e.startswith(':')
        ])
        response = ''

        for char in text:
            if emoji_count < self.max_emoji_talk_emojis:
                char = self._char_to_emoji(char)

            response += char

            if char.startswith(':'):
                emoji_count += 1

        while emj_tgs_and_plchldrs:
            i = response.find('%%')

            if i < 0:
                break

            response = (response[:i] +
                        emj_tgs_and_plchldrs.pop(0) +
                        response[i + 2:])

        return response

    def handle(self, message):
        text = html.unescape(utils.jsearch('metadata.text || text', message))
        logger.debug(f'Handling Random Emoji request: {text}')
        params = parse_message_params(
            message['text'],
            fields=['cmd', 'how_many', 'search_term']
        )
        how_many = params['how_many']

        if not how_many:
            response = self._get_emoji(
                self.default_how_many, params['search_term'])
        elif how_many == 'help':
            response = self.get_help()
        elif how_many.isdigit():
            response = self._get_emoji(int(how_many), params['search_term'])
        elif how_many == 'find':
            response = self._get_emoji(
                self.max_how_many, params['search_term'], True)
        else:
            response = self._get_emoji_talk(text[6:].strip())

        if response:
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

    def get_name(self):
        return 'Random_Emoji'

    def get_help(self):
        return ('Gets random or searched emoji. Limit 20. Usages:\n'
                '• `!emoji [optional int]` gets emoji, default 5\n'
                '• `!emoji <int> <search_term>` gets specified number of '
                'emoji that match search term\n'
                '• `!emoji find <search_term>` gets 20 emoji that match the '
                'search term\n'
                '• `!emoji <some_text>` returns "emoji talk", '
                'i.e. your text but in emoji.')
