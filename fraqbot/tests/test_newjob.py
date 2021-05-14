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
from newjob import NewJob  # noqa: E402

LOCK = threading.Lock()
BASEPLATE = Lego.start(None, LOCK)
LEGO = NewJob(BASEPLATE, LOCK)


def test_listening_for():
    # !job
    assert LEGO.listening_for({'text': 'job'}) is False
    assert LEGO.listening_for({'text': '!job moin'}) is True
    assert LEGO.listening_for({'text': '!job'}) is True
    assert LEGO.listening_for({'text': '!Job'}) is False
    # !newjob
    assert LEGO.listening_for({'text': 'newjob'}) is False
    assert LEGO.listening_for({'text': '!newjob moin'}) is True
    assert LEGO.listening_for({'text': '!newjob'}) is True
    assert LEGO.listening_for({'text': '!Newjob'}) is False


def test_get_job():
    assert bool(LEGO._get_job('')) is True
    assert bool(LEGO._get_job('developer')) is True


@patch('Legobot.Lego.Lego.reply')
@patch('newjob.NewJob._get_job')
def test_handle_check(mock_get_job, mock_reply):
    msg = {'text': '!job developer', 'metadata': {'source_user': 'eugene'}}
    LEGO.handle(msg)

    mock_get_job.assert_called_once()
    mock_reply.assert_called_once()


BASEPLATE.stop()
