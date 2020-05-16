import logging
import os
from pydoc import locate
import threading

from Legobot.Lego import Lego
import yaml


DIR = os.path.abspath(os.path.dirname(__file__))
HELP_PATH = 'Legobot.Legos.Help.Help'


def load_config(f_name=None):
    if not f_name:
        f_name = 'config.yaml'

    with open(os.path.join(DIR, f_name)) as f:
        config = yaml.safe_load(f)

    return config


def build_logger(log_file):
    if log_file:
        logging.basicConfig(filename=log_file)

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

    return logger


def initialize_baseplate():
    lock = threading.Lock()
    baseplate = Lego.start(None, lock)
    baseplate_proxy = baseplate.proxy()

    return baseplate_proxy


def add_lego(lego_config, baseplate_proxy):
    baseplate_proxy.add_child(
        locate(lego_config.get('path', '')),
        **lego_config.get('kwargs', {})
    )


def add_legos(config, baseplate_proxy):
    for lego_name, lego_config in config.items():
        if lego_config.get('enabled'):
            add_lego(lego_config, baseplate_proxy)


if __name__ == '__main__':
    # Load config
    config = load_config('config.yaml')

    # Initialize logger
    logger = build_logger(config.get('log_file'))

    # Initialize baseplate
    baseplate_proxy = initialize_baseplate()

    # Add connectors
    add_legos(config.get('connectors', {}), baseplate_proxy)

    # Add help
    add_legos(
        {'Help': {'enabled': config.get('helpEnabled'), 'path': HELP_PATH}},
        baseplate_proxy
    )

    # Add legos
    add_legos(config.get('legos', {}), baseplate_proxy)
