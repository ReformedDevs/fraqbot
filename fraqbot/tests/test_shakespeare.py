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
from shakespeare import Shakespeare  # noqa: E402

URL_BASE = 'http://localhost/files/'
LOCK = threading.Lock()
BASEPLATE = Lego.start(None, LOCK)
LEGO = Shakespeare(BASEPLATE, LOCK, url_base=URL_BASE)


def test_listening_for():
    assert LEGO.listening_for({'text': 'shake'}) is False
    assert LEGO.listening_for({'text': '!shake moin'}) is True
    assert LEGO.listening_for({'text': '!shake'}) is True


@patch('Legobot.Lego.Lego.reply')
@patch('shakespeare.Shakespeare._get_quote')
def test_handle_check(mock_get_quote, mock_reply):
    msg = {'text': '!shake face', 'metadata': {'source_user': 'bob'}}
    mock_get_quote.return_value = 'http://localhost/files/bob.jpg'
    mock_reply.return_value = "Face test"

    LEGO.handle(msg)
    mock_get_quote.assert_called_once()


BASEPLATE.stop()
