import os
import sys
import threading

from Legobot.Lego import Lego
from mock import patch

LOCAL_PATH = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '..',
    'Local'
)
sys.path.append(LOCAL_PATH)

from moin import Moin  # noqa: E402


URL_BASE = 'http://localhost/files/'
API_BASE = 'http://localhost/api/moins'
LOCK = threading.Lock()
BASEPLATE = Lego.start(None, LOCK)
LEGO = Moin(
    BASEPLATE,
    LOCK,
    url_base=URL_BASE,
    api_base=API_BASE,
    rate_config={
        'rate_key': 'metadata.source_user',
        'rate_interval': 300
    }
)


def test_listening_for():
    assert LEGO.listening_for({}) is False
    assert LEGO.listening_for({'txt': 'moin'}) is False
    assert LEGO.listening_for({'text': 'Good morning'}) is False
    assert LEGO.listening_for({'text': 'Good moin'}) is True
    assert LEGO.listening_for({'text': 'MOIN'}) is True


@patch('Legobot.Lego.Lego.reply')
@patch('moin.Moin._get_user_moin')
def test_handle_check(mock_get_user_moin, mock_reply):
    msg = {'text': 'moin', 'metadata': {'source_user': 'bob'}}
    mock_get_user_moin.return_value = 'http://localhost/files/bob.jpg'
    mock_reply.return_value = True

    LEGO.on_receive(msg)
    LEGO.on_receive(msg)
    mock_get_user_moin.assert_called_once()


BASEPLATE.stop()
