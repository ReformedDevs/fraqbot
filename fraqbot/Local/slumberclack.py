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
        path = os.path.abspath(os.path.dirname(__file__))
        self.clack_path = os.path.join(path, 'clacks.yaml')
        self.clacks = self._load_clacks(self.clack_path)
        self.clackr = re.compile('S[a-z]+C[a-z]+')
        self.honk_path = os.path.join(path, 'honks.yaml')
        self.honks = self._load_clacks(self.honk_path)
        self.honkr = re.compile('H[a-z]+G[a-z]+')

    def listening_for(self, message):
        if not isinstance(message.get('text'), str):
            return False

        self.clack_match = re.search(self.clackr, message['text'])
        self.honk_match = re.search(self.honkr, message['text'])
        return self.clack_match or self.honk_match

    def handle(self, message):
        responses = []
        if self.clack_match:
            temp = self._get_response(self.clacks)
            if temp:
                responses.append(temp)

        if self.honk_match:
            temp = self._get_response(self.honks)
            if temp:
                responses.append(temp)

        for response in responses:
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

    def _load_clacks(self, path):
        try:
            with open(path) as f:
                clacks = yaml.safe_load(f.read())

            return clacks if clacks else []
        except Exception as e:
            logger.error('There was an issue loading clacks: {}'.format(e))
            return []

    def _get_response(self, choices):
        if choices:
            return random.choice(choices)

        return None
