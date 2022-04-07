import logging
import os
from pydoc import locate
import re
import sys

from Legobot.Connectors.Slack import Slack
from Legobot.Lego import Lego


LOCAL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(LOCAL_DIR)


from helpers.file import load_file  # noqa: E402
from helpers.file import write_file  # noqa: E402
from helpers.text import tabulate_data  # noqa: E402
from helpers.utils import call_slack_api  # noqa: E402
from helpers.utils import jsearch  # noqa: E402


LOGGER = logging.getLogger(__name__)
DATA_DIR = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    'data',
    'score_boards'
)


class ScoreBoard(Lego):
    def __init__(self, baseplate, lock, *args, **kwargs):
        super().__init__(baseplate, lock, acl=kwargs.get('acl'))

        self._set_bot_thread()
        self.channels = {}
        self.boards = {}

        if not os.path.isdir(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)

        for name, cfg in kwargs.get('configs', {}).items():
            self._init_board(name, cfg)

    # Init Methods
    def _init_board(self, name, cfg):
        get_history = False
        f_type = cfg.get('file_type', 'json')
        f_name = f'{name.lower()}.{f_type}'
        cfg['path'] = os.path.join(DATA_DIR, f_name)
        data = load_file(cfg['path'], f_type=f_type, default=[])
        channels = cfg.pop('channels', ['general'])
        channels = [self.botThread.get_channel_id_by_name(c) for c in channels]

        if not os.path.isfile(cfg['path']):
            get_history = True

        for channel in channels:
            if channel not in self.channels:
                self.channels[channel] = set()

            self.channels[channel].add(name)

        self.boards[name] = {'data': data, 'config': cfg}

        if get_history is True:
            for channel in channels:
                messages = call_slack_api(
                    self.botThread.slack_client,
                    'conversations.history',
                    True,
                    'messages',
                    channel=channel
                )
                transform = ('[].{text: text, metadata: {source_channel: '
                             f'`{channel}`'
                             ', source_user: user, ts: ts}}')
                messages = jsearch(transform, messages)

                for message in messages:
                    self._process_board(message, name)

                LOGGER.debug('Channel history processed')

    def _set_bot_thread(self):
        self.botThread = None
        children = self.baseplate._actor.children

        if children:
            slack = [a._actor for a in children if isinstance(a._actor, Slack)]
            if slack:
                self.botThread = slack[0].botThread

    # Std Methods
    def listening_for(self, message):
        channel = jsearch('metadata.source_channel || `""`', message)

        if channel not in self.channels:
            return False

        for board in self.channels[channel]:
            self._process_board(message, board)

        text = message.get('text')

        if (
            isinstance(text, str)
            and (
                text.lower().startswith('!scores')
                or text.lower().startswith('!my_scores')
            )
        ):
            return True

    def handle(self, message):
        params = message['text'].split(' ')
        response = None

        if len(params) > 1 and params[1] in self.boards:
            if params[0] == '!scores':
                response = self._format_get_scores(params[1])

            elif params[0] == '!my_scores':
                user = jsearch('metadata.source_user', message)
                response = self._format_get_user_scores(params[1], user)
                message['metadata']['thread_ts'] = jsearch(
                    'metadata.thread_ts || metadata.ts',
                    message
                )

        if response:
            opts = self.build_reply_opts(message)
            self.reply(message, response, opts)

    # Action Methods
    def _get_scores(self, name):
        cfg = self.boards[name]['config']
        data = self.boards[name]['data']
        user_field = cfg.get('user_field', '')
        score_field = cfg.get('score_field', '')
        default_score = cfg.get('default_score', 0)
        uniques = {}

        for field in set(cfg.get('uid_fields', []) + [user_field]):
            uniques[field] = set([
                val for val in
                jsearch(f'[].{field}', data)
                if val
            ])

        users = uniques.pop(user_field)
        scores = []

        for user in users:
            record = {'user': user}
            user_data = jsearch(f'[?{user_field} == `"{user}"`]', data)
            record['score'] = jsearch(f'sum([].{score_field})', user_data)

            if len(uniques) == 1:
                diff = (len(list(uniques.values())[0]) - len(user_data))
                record['score'] += default_score * diff

            scores.append(record)

        sort = cfg.get('rankings_sort', '')
        (field, direction) = (s.strip() for s in sort.split(','))
        scores = sorted(
            scores,
            key=lambda k: k[field],
            reverse=direction.lower() == 'desc'
        )

        return scores

    def _get_user_scores(self, name, user):
        cfg = self.boards[name]['config']
        data = self.boards[name]['data']
        user_field = cfg.get('user_field', '')
        score_field = cfg.get('score_field', '')
        sort = cfg.get('my_scores_sort', '')
        (field, direction) = (s.strip() for s in sort.split(','))
        fltr = f'{user_field} == `"{user}"`'
        fields = f'{field}: {field}, score: {score_field}'
        transform = '[?$1].{$2}'.replace('$1', fltr).replace('$2', fields)
        scores = jsearch(transform, data)
        scores = sorted(
            scores,
            key=lambda k: k[field],
            reverse=direction.lower() == 'desc'
        )

        return scores

    def _process_board(self, message, name):
        board = self.boards[name]
        cfg = board.get('config', {})

        process = getattr(
            self, '_process_{}'.format(cfg.get('type', '')), None)

        if not process:
            return None

        record = process(message, cfg)
        updated = self._update_data(name, record)

        if updated:
            self._react(message, cfg.get('emoji', 'word'))
            self._save_data(name)

    def _process_regex(self, message, cfg):
        record = {}
        text = message.get('text', '')

        if not text or not isinstance('text', str):
            return record

        regex = re.compile(cfg.get('regex', ''))
        match = regex.search(text)

        if not match:
            return record

        condition = cfg.get('condition')

        if condition:
            condition = self._var_sub_regex(condition, match)
            cond_pass = jsearch(condition, message)

            if not cond_pass:
                return record

        transform = cfg.get('transform', '')
        transform = self._var_sub_regex(transform, match)

        if not transform:
            return record

        try:
            record = jsearch(transform, message)
        except Exception as e:
            LOGGER.info('Error transforming record.\n'
                        f'Message: {message}\n'
                        f'Transform: {transform}\n'
                        f'Error: {e}')

        return record

    def _process_script(self, message, cfg):
        record = {}
        text = message.get('text', '')

        if not text or not isinstance('text', str):
            return record

        script_path = cfg.get('script_path', '')
        script = locate(script_path)

        if not script:
            return record

        check_is_record = getattr(script, 'is_record', None)

        if not check_is_record:
            return record

        is_record = check_is_record(message, cfg)

        if not is_record:
            return record

        check_condition = getattr(script, 'check_condition', None)

        if not check_condition:
            return record

        cond_pass = check_condition(message, cfg)

        if not cond_pass:
            return record

        parse_record = getattr(script, 'parse_record', None)

        if not parse_record:
            return record

        record = parse_record(message, cfg)

        return record

    def _react(self, message, emoji):
        channel = jsearch('metadata.source_channel', message)
        ts = jsearch('metadata.ts', message)

        call_slack_api(
            self.botThread.slack_client,
            'reactions.add',
            False,
            'ok',
            channel=channel,
            name=emoji,
            timestamp=ts
        )

    def _save_data(self, name):
        cfg = self.boards[name]['config']
        f_type = cfg.get('file_type', 'json')

        if f_type in ('json', 'yaml'):
            write_file(cfg['path'], self.boards[name]['data'], f_type)

    def _update_data(self, name, record):
        if not record:
            return False

        cfg = self.boards[name]['config']
        comps = []

        for field in cfg.get('uid_fields', []):
            val = record.get(field)

            if isinstance(val, str):
                comps.append(f'{field} == `"{val}"`')
            else:
                comps.append(f'{field} == `{val}`')

        comps = ' && '.join(comps)
        query = f'[?{comps}]'
        matches = jsearch(query, self.boards[name]['data'])

        if not matches:
            self.boards[name]['data'].append(record)
            return True

        return False

    def _var_sub_regex(self, string, match):
        try:
            for var in re.findall(r'\$\{\d+\}', string):
                grp = int(var[2:-1])
                string = string.replace(var, match.group(grp))
        except Exception as e:
            LOGGER.info(f'Error in _var_sub_regex for string {string}:\n{e}')
            string = None

        return string

    # Format Methods
    def _format_get_scores(self, name):
        response = None
        scores = self._get_scores(name)

        if scores:
            response = tabulate_data(
                scores,
                {},
                user_id_field='user',
                thread=self.botThread
            )

        return response

    def _format_get_user_scores(self, name, user):
        if not user:
            return None

        scores = self._get_user_scores(name, user)

        if scores:
            response = tabulate_data(scores, {})

            return f'Score History for <@{user}>:\n{response}'
