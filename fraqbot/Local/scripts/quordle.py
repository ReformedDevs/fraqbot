import re

import jmespath


class Quordle(object):
    @staticmethod
    def is_record(message, cfg):
        text = message.get('text', '')
        match = re.match(r'Daily Quordle \d+\s', text)

        if match:
            return True

        return False

    @staticmethod
    def check_condition(message, cfg):
        text = message.get('text', '')
        match = re.match(r'Daily Quordle (\d+)\s', text)

        if match:
            puzzle = int(match.group(1))
            if not puzzle % 7 in (5, 6):
                return True

        return False

    @staticmethod
    def parse_record(message, cfg):
        text = message.get('text', '')
        _map = {
            'one': 1,
            'two': 2,
            'three': 3,
            'four': 4,
            'five': 5,
            'six': 6,
            'seven': 7,
            'eight': 8,
            'nine': 9,
            'large_red_square': 10
        }
        puzzle = re.match(r'Daily Quordle (\d+)', text)

        if not puzzle:
            return {}

        puzzle = int(puzzle.group(1))
        scores = []

        for emoji in re.findall(r':[a-z_]+:', text)[:4]:
            scores.append(_map.get(emoji[1:-1], 10))

        return {
            'user': jmespath.search(
                'metadata.source_user || `""`', message),
            'puzzle': puzzle,
            'score': sum(scores)
        }
