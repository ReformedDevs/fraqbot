import json
from Legobot.Lego import Lego
import logging
import requests

logger = logging.getLogger(__name__)
README = ('https://raw.githubusercontent.com/ReformedDevs/challenge-2019-09/'
          'master/README.md')


class Challenge(Lego):
    def listening_for(self, message):
        if message and isinstance(message, dict) and message.get('text'):
            return '!scores' in str(message['text'])

        return False

    def handle(self, message):
        # readme = self._get_readme()

        # if readme:
        #     response = self._build_response(readme)
        # else:
        #     response = 'Could not fetch leaderboard.'

        results = self._get_json()
        if results:
            response = self._build_response(results)
        else:
            response = 'Could not fetch leaderboard.'

        opts = self.build_reply_opts(message)
        if response:
            self.reply(message, response, opts=opts)

    def _get_json(self):
        url = ('https://raw.githubusercontent.com/ReformedDevs/'
               'challenge-2019-10/master/test_results.json')
        get_json = requests.get(url)
        code = get_json.status_code
        text = get_json.text
        logger.debug(f'HTTP request: {code}: {url}')
        if code != requests.codes.ok:
            return None

        return json.loads(text).get('Overall Rankings')

    def _get_readme(self):
        get_readme = requests.get(README)
        if get_readme.status_code == requests.codes.ok:
            return get_readme.text

        return None

    def _build_response(self, readme):
        # table = self._get_md_table(readme, '### Leaderboard')
        # if not table:
        #     return None

        # obj = self._md_to_obj(table)
        # if not obj:
        #     return None
        fields = ['Author', 'Language', 'Time (ms)', 'Notes']
        obj = readme

        board = self._obj_to_pretext(obj, field_order=fields)
        if board:
            return f'*CHALLENGE 2019-10*```{board}```'

        return None

    def _md_to_obj(self, md):
        lines = md.splitlines()
        if len(lines) < 3:
            return None

        out = []
        keys = [k.strip() for k in lines[0].split('|')]
        if lines[1].startswith('---'):
            lines.pop(1)

        for ln in lines[1:]:
            rec = {}
            items = [i.strip() for i in ln.split('|')]
            for i, k in enumerate(keys):
                rec[k] = items[i]

            out.append(rec)

        return out

    def _get_md_table(self, md, header):
        if header not in md:
            return None

        h_pos = md.find(header)
        lines = md[h_pos:].splitlines()
        out = []
        for ln in lines:
            if not out and '|' in ln:
                out.append(ln)
            elif out and '|' in ln:
                out.append(ln)
            elif out and '|' not in ln:
                break

        if not out:
            return None

        return '\n'.join(out)

    def _obj_to_pretext(self, obj, field_order=None, just_map=None,
                        type_map=None, sort_field=None, sort_dir=None):
        if not obj or not isinstance(obj, list):
            return None

        if not isinstance(obj[0], dict):
            return None

        if sort_field:
            obj = sorted(obj, key=lambda k: k.get(sort_field))

        keys = field_order if field_order else list(obj[0].keys())
        lengths = {
            k: max([len(str(o.get(k, ''))) for o in obj] + [len(str(k))]) + 2
            for k in keys
        }
        lines = []
        header = '|'.join([
            self._justify(k, lengths.get(k, len(k)), 'center')
            for k in keys
        ])
        lines.append(header)
        d = ''
        line_length = sum([v for k, v in lengths.items()]) + len(lengths) - 1
        while len(d) < line_length:
            d += '-'

        lines.append(d)

        for o in obj:
            vals = []
            for k in keys:
                p = 1
                if k == keys[0]:
                    d = 'left'
                elif k == keys[-1]:
                    d = 'right'
                else:
                    d = 'center'
                    p = None
                ls = lengths.get(k, len(k))
                vals.append(self._justify(o.get(k, ''), ls, d, p))

            lines.append('|'.join(vals))

        return '\n'.join(lines)

    def _justify(self, text, length, dir, pad=None):
        text = str(text)
        if pad is None:
            pad = 0

        if len(text) + 2 > length:
            return None

        if dir == 'left':
            for _ in range(pad):
                text = ' ' + text

            while len(text) < length:
                text += ' '

            return text

        if dir == 'right':
            for _ in range(pad):
                text += ' '

            while len(text) < length:
                text = ' ' + text

            return text

        if dir == 'center':
            i = 1
            while len(text) < length:
                if i % 2 == 1:
                    text += ' '
                elif i % 2 == 0:
                    text = ' ' + text
                i += 1

            return text

        return text

    def get_name(self):
        return 'Challenge Scores'

    def get_help(self):
        return ('Get monthly challenge leaderboard by typing `!scores` in '
                'any message.')
