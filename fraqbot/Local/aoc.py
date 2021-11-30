import argparse
from decimal import Decimal
import logging
import os
import re
import sys

import jmespath

from Legobot.Connectors.Slack import Slack
from Legobot.Lego import Lego

LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
if LOCAL_DIR not in sys.path:
    sys.path.append(LOCAL_DIR)

from helpers.file import load_file  # noqa 402
from helpers.utils import call_rest_api  # noqa 402
from helpers.text import format_table  # noqa 402

logger = logging.getLogger(__name__)
TWOPLACES = Decimal(10) ** -2


class AOC(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        children = self.baseplate._actor.children
        if children:
            slack = [a._actor for a in children if isinstance(a._actor, Slack)]
            if slack:
                self.botThread = slack[0].botThread

        self.cookie = kwargs.get('cookie')
        self.year = kwargs.get('year', '2021')
        self.board = kwargs.get('board')
        self._init_user_map()
        self._init_parser()

    def listening_for(self, message):
        text = message.get('text', '')
        if not isinstance(text, str) or not self.cookie:
            return False

        return text.lower().startswith('!aoc')

    def handle(self, message):
        response = self._build_response(message['text'])
        if response:
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

    def _init_user_map(self):
        self.user_map = load_file(
            os.path.join(LOCAL_DIR, 'data', 'aoc_map.yaml'))

    def _init_parser(self):
        self.parser = argparse.ArgumentParser(
            prog='!aoc',
            description='Retrieve TRD\'s Advent of Code leaderboard.',
            add_help=False
        )
        self.parser.add_argument(
            '-h',
            '--help',
            action='store_true',
            help='show this help message and exit'
        )
        self.parser.add_argument(
            '-y',
            '--year',
            type=str,
            help='What year to retrieve. Defaults to the current year.',
            default=self.year
        )
        self.parser.add_argument(
            '-c',
            '--column',
            type=str,
            help='Which column to sort the data on. Defaults to score.',
            choices=['name', 'score', 'stars', 'pika'],
            default='score'
        )
        self.parser.add_argument(
            '-s',
            '--sort',
            type=str,
            help='Which direction to sort the data. Defaults to DESC.',
            choices=['ASC', 'DESC'],
            default='DESC'
        )

    def _get_leaderboard(self, year):
        headers = {'Cookie': self.cookie}
        url = (f'https://adventofcode.com/{year}/leaderboard/private/view'
               f'/{self.board}.json')
        return call_rest_api(
            __name__, 'get', url, response='json', headers=headers)

    def _sort_leaderboard(self, leaderboard, sort_key, direction):
        reverse = direction == 'DESC'
        srch = ('[].{name: slack_name, score: local_score, '
                'stars: stars, pika: pika}')
        leaders = sorted(
            jmespath.search(srch, leaderboard),
            key=lambda k: k[sort_key],
            reverse=reverse
        )

        return leaders

    def _get_slack_name(self, _id, name):
        if _id in self.user_map:
            name = self.botThread.get_user_name_by_id(
                self.user_map[_id], True, name)

        return name

    def _build_response(self, message):
        params = re.split(r'\s+', message)
        params.pop(0)
        args = self.parser.parse_args(params)

        if args.help:
            return self.get_help()

        leaderboard = self._get_leaderboard(args.year)
        logger.debug('LEADERBOARD: {}'.format(leaderboard))
        if leaderboard:
            new = []
            for k, v in leaderboard.get('members', {}).items():
                if v.get('stars', 0) > 0:
                    v.update({
                        'id': k,
                        'slack_name': self._get_slack_name(v['id'], v['name'])
                    })
                    new.append(v)

            leaderboard = self._calculate_suplemental_values(new)
            leaders = self._sort_leaderboard(
                leaderboard, args.column, args.sort)

            fields = [
                {'field': 'name', 'display': 'NAME'},
                {'field': 'score', 'display': 'SCORE'},
                {'field': 'stars', 'display': 'STARS'},
                {'field': 'pika', 'display': 'PIKADEX'}
            ]
            leaders = format_table(leaders, fields=fields, sep='   ')

            return f'```{leaders}```'
        else:
            return None

    def _calculate_suplemental_values(self, leaderboard):
        if not leaderboard:
            return leaderboard

        pika = [
            {'stars': x['stars'], 'score': x['local_score']}
            for x in leaderboard
            if x['name'] == 'Patrick Carver'
        ]
        pika = pika[0] if pika else{'score': 0, 'stars': 0}
        max_stars = max(x['stars'] for x in leaderboard)
        for item in leaderboard:
            item['pika'] = self._calculate_pikadex(
                item['local_score'],
                pika['score'],
                item['stars'],
                pika['stars'],
                max_stars
            )

        return leaderboard

    def _calculate_pikadex(self, score, p_score, stars, p_stars, max_stars):
        star_mod = stars - p_stars
        score_mod = score - p_score
        return Decimal((star_mod * score_mod) / max_stars).quantize(TWOPLACES)

    def get_name(self):
        return 'AOC'

    def get_help(self):
        return f'```{self.parser.format_help()}```'
