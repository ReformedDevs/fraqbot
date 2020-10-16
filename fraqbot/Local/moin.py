import logging
import os
import sys
import time

from Legobot.Lego import Lego

LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
if LOCAL_DIR not in sys.path:
    sys.path.append(LOCAL_DIR)

from helpers import call_rest_api  # noqa #402


logger = logging.getLogger(__name__)


class Moin(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self.url_base = kwargs.get('url_base')
        self.api_base = kwargs.get('api_base')
        self.rate_map = {}

    def _get_user_moin(self, user):
        url = f'{self.api_base}/{user}'
        f_name = call_rest_api(__name__, 'get', url, response='json')
        if f_name:
            return f'{self.url_base}{f_name}'
        else:
            return None

    def _check_rate(self, source_user):
        if not source_user:
            return False

        now = int(time.time())
        last = self.rate_map.get(source_user, 0)
        if now - last >= 300:
            self.rate_map[source_user] = now
            return True

        return False

    def listening_for(self, message):
        return 'moin' in str(message.get('text', '')).lower()

    def handle(self, message):
        source_user = message.get('metadata', {}).get('source_user', '')
        logger.debug(f'HANDLING MOIN for {source_user}')
        check = self._check_rate(source_user)
        logger.debug(f'CHECK RATE for {source_user}: {check}')
        if check:
            moin = self._get_user_moin(source_user)
            if moin:
                opts = self.build_reply_opts(message)
                self.reply_attachment(message, 'moin', moin, opts=opts)

    def get_name(self):
        return ''
