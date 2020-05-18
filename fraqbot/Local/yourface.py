import logging
import os
import random

from Legobot.Lego import Lego

from .helpers import call_rest_api


logger = logging.getLogger(__name__)


class YourFace(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self.token = kwargs.get('token')
        self.api = kwargs.get('api', '')
        self.url_base = kwargs.get('url_base', '')
        files = os.listdir(
            os.path.join(
                os.path.abspath(
                    os.path.dirname(__file__)
                ),
                'cheats'
            )
        )
        self.faces = [{'link': self.url_base + f, 'count': 0}
                      for f in files if not f.startswith('.')]
        self.counter = 0
        logger.debug(self.faces)
        self.error_responses = [
            'Your face is offline.',
            'Your face is an internal server error.',
            'Your face is unauthorized.',
            'Your face is not found.',
            'Your face is a bad request.',
            'Your face is forbidden.'
        ]

    def listening_for(self, message):
        if 'your face is' in str(message.get('text')):
            self.counter += 1
            return True

        return False

    def handle(self, message):
        opts = self.build_reply_opts(message)
        text_response = self._get_your_face_quote()
        if text_response:
            if self.counter % 3 == 0:
                self._reply_pikachu(text_response, message, opts)
            else:
                self.reply(message, text_response, opts)

    def _get_your_face_quote(self):
        quote = call_rest_api(__name__, 'get', self.api, response='json')
        quote = quote.get('quote')

        if not quote:
            quote = random.choice(self.error_responses)

        return quote

    def _reply_pikachu(self, text, message, opts):
        self.faces = sorted(self.faces, key=lambda k: k['count'])
        url = self.faces[0]['link']
        self.faces[0]['count'] += 1
        self.reply_attachment(message, text, url, opts=opts)

    def get_name(self):
        return ''
