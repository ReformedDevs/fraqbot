from Legobot.Lego import Lego
import requests
import logging
import json
import random

logger = logging.getLogger(__name__)


class XKCD(Lego):
    def listening_for(self, message):
        return str(message.get('text')).lower().startswith('!xkcd')

    def handle(self, message):
        comic_id = self._parse_args(message)
        url = self._build_url(comic_id)

        if url:
            logger.info('Retrieving URL: {}'.format(url))
            text, attachment = self._get_comic(url)
            
            if text:
                opts = self.build_reply_opts(message)
                if attachment:
                    self.reply_attachment(message, text, attachment, opts)
                else:
                    self.reply(message, text, opts)

    def _parse_args(self, message):
        comic_id = None
        words = message['text'].split()
        if len(words) > 1:
            comic_id = words[1]

        return comic_id

    def _build_url(self, comic_id):
        url = 'http://xkcd.com'
        if comic_id:
            if comic_id == 'r' or comic_id == 'random':
                comic_id = self._get_random_comic_id()

            url += f'/{comic_id}'

        url += '/info.0.json'

        return url

    def _get_random_comic_id(self):
        latest = requests.get('http://xkcd.com/info.0.json')
        if latest.status_code == requests.codes.ok:
            latest_json = json.loads(latest.text)
            comic_id = random.randint(1, latest_json['num'])  # nosec
        else:
            logger.error('Requests encountered an error.')
            logger.error('''HTTP GET response code:
                        {}'''.format(latest.status_code))
            comic_id = 1337
        return comic_id

    def _get_comic(self, url):
        get_comic = requests.get(url)
        if get_comic.status_code == requests.codes.ok:
            return self._parse_for_comic(json.loads(get_comic.text))
        else:
            logger.error(f'{get_comic.status_code}: {get_comic.txt}')
            return None, None

    def _parse_for_comic(self, comic):
        if comic:
            text = ' '
            attachment = {
                'pre_text': '*#{}: {}*'.format(comic['num'], comic['title']),
                'url': comic['img'],
                'post_text': '_{}_'.format(
                    comic['alt'].replace(comic['img'], ''))
            }
            return text, attachment
        else:
            logger.error('Unable to find a comic')
            return 'Unable to find a comic', {}

    def get_name(self):
        return 'xkcd'

    def get_help(self):
        return 'Fetch an xkcd. Usage: !xkcd [r|random|int]'
