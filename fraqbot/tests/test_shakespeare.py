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

LOCK = threading.Lock()
BASEPLATE = Lego.start(None, LOCK)
LEGO = Shakespeare(BASEPLATE, LOCK)


def test_listening_for():
    assert LEGO.listening_for({'text': 'shake'}) is False
    assert LEGO.listening_for({'text': '!shake moin'}) is True
    assert LEGO.listening_for({'text': '!shake'}) is True
    assert LEGO.listening_for({'text': '!Shake'}) is False


def test_get_quote():
    default = 'Not so much brain as ear wax.'
    assert LEGO._get_quote('') == default
    assert LEGO._get_quote('bad search') == default
    assert LEGO._get_quote('scurvy') == '11. I scorn you, scurvy companion.'


@patch('Legobot.Lego.Lego.reply')
@patch('shakespeare.Shakespeare._get_quote')
def test_handle_check(mock_get_quote, mock_reply):
    msg = {'text': '!shake scurvy', 'metadata': {'source_user': 'bob'}}
    LEGO.handle(msg)

    mock_get_quote.assert_called_once()
    mock_reply.assert_called_once()


BASEPLATE.stop()
