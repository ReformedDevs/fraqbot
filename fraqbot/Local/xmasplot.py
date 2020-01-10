import json
from Legobot.Lego import Lego
import logging
import requests

logger = logging.getLogger(__name__)


class XMasPlot(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock)
        self.api = kwargs.get('api', '')

    def listening_for(self, message):
        if message.get('text'):
            try:
                return message.get('text').startswith('!plot')
            except Exception as e:
                logger.error(('XMasPlot failed to check the message text:'
                             ' {}').format(e))
                return False

    def handle(self, message):
        opts = self.build_reply_opts(message)
        response = self._build_response()
        if response:
            self.reply(message, response, opts)

    def _build_response(self):
        get_plot = requests.get(self.api)
        if get_plot.status_code == requests.codes.ok:
            return json.loads(get_plot.text)['quote']
        else:
            return None

    def get_name(self):
        return 'XMasPlot'

    def get_help(self):
        return 'Get an AI generated Christmas movie plot. Usage: !plot.'
