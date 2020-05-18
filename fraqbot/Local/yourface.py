import json
import logging
import os
import random

from Legobot.Lego import Lego
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


class YourFace(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self.token = kwargs.get('token')
        self.api = kwargs.get('api', '')
        self.url_base = kwargs.get('url_base', '')
        self.post_payload = {
            'as_user': True,
            'text': '',
            'channel': '#bot-babble',
            'attachments': [
                {
                    'fallback': 'your face',
                    'image_url': f'{self.url_base}reynold.png'
                }
            ]
        }
        self.post_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        self.post_url = 'https://slack.com/api/chat.postMessage'
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
        if message.get('text') and message['metadata'].get('display_name'):
            try:
                text = message.get('text').lower()
                if 'your face is' in text:
                    self.counter += 1
                    return True
            except Exception as e:
                logger.error(('YourFace failed to check the message text:'
                             ' {}').format(e))
                return False

    def handle(self, message):
        opts = self.build_reply_opts(message)
        text_response = self._get_your_face_quote()
        if text_response:
            self.reply(message, text_response, opts)

        if self.counter % 3 == 0:
            self._post_pikachu(message)

    def _get_your_face_quote(self):
        try:
            get_quote = requests_retry_session().get(self.api)
            logger.debug('Quotes API response: {}: {}'.format(
                get_quote.status_code, get_quote.text))
            if get_quote.status_code == requests.codes.ok:
                return json.loads(get_quote.text)['quote']
            else:
                return random.choice(self.error_responses)
        except Exception as e:
            logger.debug(e)
            return random.choice(self.error_responses)

    def _post_pikachu(self, message):
        self.post_payload['channel'] = message['metadata']['source_channel']
        self.faces = sorted(self.faces, key=lambda k: k['count'])
        self.post_payload['attachments'][0]['image_url'] = self.faces[0]['link']
        self.faces[0]['count'] += 1
        post = requests.post(
            self.post_url,
            headers=self.post_headers,
            data=json.dumps(self.post_payload)
        )
        msg = '\nSLACK API CALL\nRESPONSE CODE: {}\nRESPONSE TEXT: {}'.format(
            post.status_code, post.text
        )
        if post.status_code == requests.codes.ok:
            logger.debug(msg)
        else:
            logger.error(msg)

    def get_name(self):
        return ''
