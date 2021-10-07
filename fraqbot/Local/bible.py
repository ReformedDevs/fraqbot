from Legobot.Lego import Lego
import logging
import requests

logger = logging.getLogger(__name__)


class Bible(Lego):
    def listening_for(self, message):
        return message['text'].split()[0] == '!bible'

    def split_maybe(self, string, on, expected):
        _split = []
        if on in string:
            _split = string.split(on)
        else:
            _split = [string]
        for _ in range(expected - len(_split)):
            _split.append("")
        return _split


    def parse_message(self, message_text):
        _, book, ref, ver = self.split_maybe(message_text, " ", 4)
        chapter, verses = self.split_maybe(ref, ':', 2)
        v_start, v_end = self.split_maybe(verses, '-', 2)
        if not all(x.isdigit() for x in [chapter, v_start, v_end] if x):
            logger.error(f"Chapter requested is malformed: {chapter}")
            return ""
        passage = book + chapter
        if v_start:
            passage += ":" + v_start
        if v_end:
            passage += "-" + v_end
        if ver.lower() in ["web", "kjv", "vul", "pr"]:
            passage += "?translation=" + ver
        return passage


    def get_text(self, verses):
        if len(verses) == 1:
            verses = ' '.join(verses[0]['text'].split())
        else:
            verses = '\n'.join([f"{x['verse']}: {' '.join(x['text'].split())}" for x in verses])
        return verses

    def handle(self, message):
        logger.debug('Handling Bibile request: {}'.format(message['text']))
        try:
            target = message['metadata']['source_channel']
            opts = {'target': target}
        except IndexError:
            logger.error('''Could not identify message source in message:
                        {}'''.format(str(message)))

        base_url = 'https://bible-api.com/'
        passage = self.parse_message(message['text'])

        logger.debug('Calling Bible API: {}{}'.format(base_url, passage))
        r = requests.get(base_url + passage)

        if r.status_code == requests.codes.ok:
            logger.debug('Bible API responded positively.')
            reference = r.json()['reference']
            verses = r.json()['verses']
            text = self.get_text(verses)
            self.reply(message, reference + ':\n' + text, opts)
        else:
            logger.error('Requests encountered an error.')
            logger.error('''HTTP GET response code:
                        {}'''.format(r.status_code))

    def get_name(self):
        return 'Bible'

    def get_help(self):
        help_text = ('Get Bible references using bible-api.com. '
                     'The WEB translation is the default. '
                     'Usage: !bible <book> <chapter>:<verse(s)> <translation>'
                     'Translations include "web", "kjv", Latin ("vul"), and '
                     'João Ferreira de Almeida ("pr").'
                     'Checkout github.com/pard68/legos.bible for more info')
        return help_text
