import json
import logging

from Legobot.Lego import Lego
import requests


logger = logging.getLogger(__name__)


class UrbanDictionary(Lego):
    def listening_for(self, message):
        if not isinstance(message.get('text'), str):
            return False

        return message['text'].startswith('!ud ')

    def _parse_response(self, response):
        text = None
        items = response.get('list', [])
        if items:
            text = items[0].get('definition', '')
            text = text.replace('[', '').replace(']', '')

        return text if text else None

    def _get_definition(self, term):
        url = f'https://api.urbandictionary.com/v0/define?term={term}'
        get_def = requests.get(url)
        if get_def.status_code == requests.codes.ok:
            return self._parse_response(json.loads(get_def.text))
        else:
            logger.error(f'Error calling {url}. {get_def.status_code}'
                         f': {get_def.text}')
            return None

    def handle(self, message):
        term = message['text'][4:]
        if term:
            response = self._get_definition(term)
            if response:
                opts = self.build_reply_opts(message)
                self.reply(message, response, opts=opts)

    def get_name(self):
        return 'UrbanDictionary'

    def get_help(self):
        return 'Search Urban Dictionary. May be NSFW. Usage: !ud [search term]'
