import json
import logging
import re

from Legobot.Lego import Lego
import requests


logger = logging.getLogger(__name__)


class UrbanDictionary(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self.censors = kwargs.get('censors', [])

    def listening_for(self, message):
        if not isinstance(message.get('text'), str):
            return False

        return any([
            message['text'].startswith('!ud '),
            message['text'].startswith('/mangle ')
        ])

    def _censor(self, text):
        for c in self.censors:
            fnd = re.compile(c['fnd'], re.IGNORECASE)
            text = re.sub(fnd, c['sub'], text)

        return text

    def _parse_response(self, response, index):
        text = None
        items = response.get('list', [])
        if index == '%':
            import random
            index = random.randint(0, len(items) - 1)
        if items:
            try:
                text = items[index].get('definition', '')
            except IndexError:
                text = items[0].get('definition', '')
            text = text.replace('[', '').replace(']', '')
            text = self._censor(text)

        return text if text else None

    def _get_definition(self, term, index):
        url = f'https://api.urbandictionary.com/v0/define?term={term}'
        get_def = requests.get(url)
        if get_def.status_code == requests.codes.ok:
            return self._parse_response(json.loads(get_def.text), index)
        else:
            logger.error(f'Error calling {url}. {get_def.status_code}'
                         f': {get_def.text}')
            return None

    def handle(self, message):
        if message['text'].startswith('!ud'):
            try:
                term, index = message['text'][4:].split("#")
            except ValueError:
                term = message['text'][4:]
        elif message['text'].startswith('/mangle'):
            term = message['text'][8:]
        else:
            term = ''

        if term:
            if not index:
                index = 0
            response = self._get_definition(term, index)
            if response:
                opts = self.build_reply_opts(message)
                self.reply(message, response, opts=opts)

    def get_name(self):
        return 'UrbanDictionary'

    def get_help(self):
        return 'Search Urban Dictionary. May be NSFW. Usage: !ud [search term]'
