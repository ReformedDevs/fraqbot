import logging
import os
import sys

from Legobot.Lego import Lego

LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
if LOCAL_DIR not in sys.path:
    sys.path.append(LOCAL_DIR)

from helpers.utils import call_rest_api  # noqa E402
from helpers.utils import is_delete_event  # noqa E402


logger = logging.getLogger(__name__)


class Moin(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(
            baseplate,
            lock,
            acl=kwargs.get('acl'),
            rate_config=kwargs.get('rate_config')
        )
        self.url_base = kwargs.get('url_base')
        self.api_base = kwargs.get('api_base')

    def _get_user_moin(self, user):
        url = f'{self.api_base}/{user}'
        f_name = call_rest_api(__name__, 'get', url, response='json')
        if f_name:
            return f'{self.url_base}{f_name}'
        else:
            return None

    def listening_for(self, message):
        if is_delete_event(message):
            return False

        return 'moin' in str(message.get('text', '')).lower()

    def handle(self, message):
        source_user = message.get('metadata', {}).get('source_user', '')
        logger.debug(f'HANDLING MOIN for {source_user}')
        moin = self._get_user_moin(source_user)
        if moin:
            opts = self.build_reply_opts(message)
            self.reply_attachment(message, 'moin', moin, opts=opts)

    def get_name(self):
        return ''
