import logging
import os
import re

from Legobot.Lego import Lego
import random
import yaml


logger = logging.getLogger(__name__)


class SlumberClack(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock)
        self.clack_path = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'clacks.yaml')
        self.clacks = self._load_clacks()
        self.r = re.compile('S[a-z]+C[a-z]+')

    def listening_for(self, message):
        if not isinstance(message.get('text'), str):
            return False

        return re.search(self.r, message['text'])

    def handle(self, message):
        response = self._get_response()
        if response:
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

    def _load_clacks(self):
        try:
            with open(self.clack_path) as f:
                clacks = yaml.safe_load(f.read())

            return clacks if clacks else []
        except Exception as e:
            logger.error('There was an issue loading clacks: {}'.format(e))
            return []

    def _get_response(self):
        if self.clacks:
            return random.choice(self.clacks)

        return None
