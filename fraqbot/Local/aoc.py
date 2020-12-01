from decimal import Decimal
import json
from Legobot.Lego import Lego
import logging
import requests

logger = logging.getLogger(__name__)
TWOPLACES = Decimal(10) ** -2


class AOC(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))
        self.cookie = kwargs.get('cookie')
        self.year = kwargs.get('year')
        self.board = kwargs.get('board')

    def listening_for(self, message):
        if message.get('text') and self.cookie:
            try:
                return message.get('text').lower().startswith('!aoc')
            except Exception as e:
                logger.error(('AOC lego failed to check the message text:'
                             ' {}').format(e))
                return False

    def handle(self, message):
        opts = self.build_reply_opts(message)
        response = self._build_response(message['text'])
        if response:
            self.reply(message, response, opts)

    def _get_leaderboard(self):
        headers = {'Cookie': self.cookie}
        url = (f'https://adventofcode.com/{self.year}/leaderboard/private/view'
               f'/{self.board}.json')
        get_leaderboard = requests.get(url, headers=headers)
        if get_leaderboard.status_code == requests.codes.ok:
            return json.loads(get_leaderboard.text)
        else:
            logger.warning(
                'GET LEADERBOARD FAILED. CODE: {}. MESSAGE {}.'.format(
                    get_leaderboard.status_code,
                    get_leaderboard.text
                )
            )
            return None

    def _build_response(self, message):
        sort_key_map = {
            'score': 'score',
            'stars': 'stars',
            'name': 'name',
            'crank': 'crank',
            'chuck': 'crank'
        }
        reverse_map = {
            'asc': False,
            'desc': True
        }
        if len(message.split(' ')) > 2:
            reverse = message.split(' ')[2].lower()
        else:
            reverse = 'desc'

        if len(message.split(' ')) > 1:
            sort_key = message.split(' ')[1].lower()
            if sort_key in reverse_map.keys():
                reverse = sort_key
                sort_key = 'score'
        else:
            sort_key = 'score'

        reverse = reverse_map.get(reverse, True)
        sort_key = sort_key_map.get(sort_key, 'local_score')
        leaderboard = self._get_leaderboard()
        logger.debug('LEADERBOARD: {}'.format(leaderboard))
        if leaderboard:
            leaderboard = {
                k: v for k, v in leaderboard.get('members', {}).items()
                if v.get('stars', 0) > 0
            }
            # leaderboard.get('members')
            leaderboard = self._calculate_suplemental_values(leaderboard)
            leaders = sorted(
                        [{'name': value['name'],
                          'score': value['local_score'],
                          'stars': value['stars'],
                          'crank': value['crank']}
                         for k, value in leaderboard.items()],
                        key=lambda k: k[sort_key],
                        reverse=reverse)
            leaders.insert(0, {
                'name': 'NAME',
                'score': 'SCORE',
                'stars': 'STARS',
                'crank': 'CHUCK INDEX'
            })
            max_len = {
                'name': max([len(str(x['name'])) for x in leaders]) + 3,
                'score': max([len(str(x['score'])) for x in leaders]) + 3,
                'stars': max([len(str(x['stars'])) for x in leaders]) + 3,
                'crank': max([len(str(x['crank'])) for x in leaders]) + 3
            }
            display_order = [
                'name',
                'score',
                'stars',
                'crank'
            ]
            if sort_key != 'name':
                display_order.remove(sort_key)
                display_order.insert(1, sort_key)

            table = ''
            for x in leaders:
                x = {k: str(v) for k, v in x.items()}
                for cat in display_order:
                    while len(x[cat]) < max_len[cat]:
                        x[cat] += ' '
                    table += x[cat]
                table += '\n'

            response = '```{}```'.format(table)
            return response
        else:
            return None

    def _calculate_suplemental_values(self, leaderboard):
        chuck = [
            {'stars': x['stars'], 'score': x['local_score']}
            for k, x in leaderboard.items()
            if x['name'] == 'sircharleswatson'
        ]
        chuck = chuck[0] if chuck else {'score': 0, 'stars': 0}
        for k, v in leaderboard.items():
            v['crank'] = self._calculate_chuck_rank(
                v['local_score'],
                chuck['score'],
                v['stars'],
                chuck['stars'],
                max(v['stars'] for k, v in leaderboard.items())
            )

        return leaderboard

    def _calculate_chuck_rank(self, score, chuck_score, stars, chuck_stars,
                              max_stars):
        star_mod = stars - chuck_stars
        score_mod = score - chuck_score
        return Decimal((star_mod * score_mod) / max_stars).quantize(TWOPLACES)

    def get_name(self):
        return 'AOC'

    def get_help(self):
        return ('Returns Advent of Code private leaderboard info.\n Usage !aoc'
                ' [sort column] [sort direction]\nColumns: name, score, stars,'
                ' chuck\nDirections: asc, desc')
