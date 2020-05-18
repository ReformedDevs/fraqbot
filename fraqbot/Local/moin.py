import json
import logging

from Legobot.Lego import Lego
import requests

from .helpers import call_rest_api


logger = logging.getLogger(__name__)


class Moin(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self.url_base = kwargs.get('url_base')
        self.api_base = kwargs.get('api_base')
        self._update_acl()

    def _update_acl(self):
        if not self.acl:
            self.acl = {}

        if 'whitelist' not in self.acl:
            self.acl['whitelist'] = sorted([
                k for k in
                self._call_api('get', self.api_base).keys()
            ])

    def _call_api(self, method, url, payload=None):
        if method == 'get':
            response = requests.get(url)
            if response.status_code == requests.codes.ok:
                response = json.loads(response.text)
            else:
                response = None
        else:
            response = None

        return response

    def _get_user_moin(self, user):
        url = f'{self.api_base}/{user}'
        f_name = call_rest_api(__name__, 'get', url, response='json')
        if f_name:
            return f'{self.url_base}{f_name}'
        else:
            return None

    def listening_for(self, message):
        return 'moin' in str(message.get('text')).lower()

    def handle(self, message):
        moin = self._get_user_moin(message['metadata']['source_user'])
        if moin:
            opts = self.build_reply_opts(message)
            self.reply_attachment(message, 'moin', moin, opts=opts)

    def get_name(self):
        return ''
