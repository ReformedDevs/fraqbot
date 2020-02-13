import logging
import os
import threading

from Legobot.Connectors.Slack import Slack
from Legobot.Lego import Lego
from Legobot.Legos.Help import Help
from legos.apod import APOD
# from legos.dice import Roll
from legos.fact_sphere import FactSphere
from legos.memes import Memes
# from legos.stocks import Cryptocurrency
# from legos.wtf import WikipediaTopFinder
from legos.xkcd import XKCD
import yaml

# from Local.aoc import AOC
from Local.bible import Bible
from Local.challenge import Challenge
from Local.dictator import Dictator
from Local.moin import Moin
from Local.slumberclack import SlumberClack
from Local.xmasplot import XMasPlot
from Local.yourface import YourFace


# load configs
DIR = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(DIR, 'config.yaml')) as f:
    config = yaml.safe_load(f)

slack_token = config.get('slackToken')
apod_key = config.get('apodKey')
aoc_cookie = config.get('aocCookie')
aoc_year = config.get('aocYear')
aoc_board = config.get('aocBoard')
moin_base = config.get('moinBase')
meme_config = config.get('memes', {})
xmas_api = config.get('xmasApi')
your_face_api = config.get('yourFaceApi')
your_face_base = config.get('yourFaceBase')

# setup logging
logging.basicConfig(filename='/tmp/logs/fraqbot.log')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(ch)

# Initialize lock and baseplate
lock = threading.Lock()
baseplate = Lego.start(None, lock)
baseplate_proxy = baseplate.proxy()

# Add children
baseplate_proxy.add_child(Slack, token=slack_token)
baseplate_proxy.add_child(Help)
# baseplate_proxy.add_child(Roll)
# baseplate_proxy.add_child(WikipediaTopFinder)
baseplate_proxy.add_child(XKCD)
# baseplate_proxy.add_child(Cryptocurrency)
baseplate_proxy.add_child(Memes, **meme_config)
baseplate_proxy.add_child(APOD, key=apod_key)
baseplate_proxy.add_child(FactSphere)
baseplate_proxy.add_child(Moin, url_base=moin_base)
baseplate_proxy.add_child(
    YourFace, token=slack_token, api=your_face_api, url_base=your_face_base)
# baseplate_proxy.add_child(
#     AOC, cookie=aoc_cookie, year=aoc_year, board=aoc_board)
# baseplate_proxy.add_child(Wat)
baseplate_proxy.add_child(SlumberClack, config=config.get('SlumberClack', {}))
baseplate_proxy.add_child(XMasPlot, api=xmas_api)
baseplate_proxy.add_child(Challenge)
baseplate_proxy.add_child(Dictator, config=config.get('Dictator', {}))
baseplate_proxy.add_child(Bible)
