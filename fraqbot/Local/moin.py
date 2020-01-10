from Legobot.Lego import Lego
import logging
import requests
import time
import yaml

logger = logging.getLogger(__name__)


class Moin(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock)
        self.url_base = kwargs.get('url_base')
        self.load_map(5)

    def load_map(self, retries):
        config_url = f'{self.url_base}moins.yaml'
        get_map = requests.get(config_url)
        if get_map.status_code == requests.codes.ok:
            self.image_map = yaml.safe_load(get_map.text)
        elif retries > 0:
            self.load_map(retries - 1)
        else:
            self.image_map = {}

        self.map_timestamp = int(round(time.time()))

    def listening_for(self, message):
        if message.get('text') and message['metadata'].get('display_name'):
            try:
                text = message.get('text').lower()
                user = message['metadata'].get('display_name')
                if 'moin' in text and user in self.image_map.keys():
                    return True
            except Exception as e:
                logger.error(('LegoName lego failed to check the message text:'
                             ' {}').format(e))
                return False

    def handle(self, message):
        if int(round(time.time())) > self.map_timestamp + 300:
            self.load_map(5)

        opts = self.build_reply_opts(message)
        attachment = self.image_map.get(
            message['metadata'].get('display_name', 'None'),
            f'{self.url_base}moin.jpg'
        )
        self.reply_attachment(message, 'moin', attachment, opts=opts)

    def get_name(self):
        return ''
