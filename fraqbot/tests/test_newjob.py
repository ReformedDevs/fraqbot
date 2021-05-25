import os
import re
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
    assert isinstance(LEGO._get_job(''), str)
    assert isinstance(LEGO._get_job('developer'), str)
    assert isinstance(LEGO._get_job('Mercedes-Benz U.S. International'), str)
    assert 'Dreamland Bar-B-Que' in LEGO._get_job('Dreamland Bar-B-Que')
    # 5 instances (modifier, role, company, link, link text)
    assert len(re.findall('Management', LEGO._get_job('Management'))) >= 5
    assert len(re.findall('Management', LEGO._get_job('MANAGEMENT'))) >= 5
    assert len(re.findall('Management', LEGO._get_job('management'))) >= 5
    # multi search functionality
    assert len(re.findall(
            '^Lead Farmer at Mercedes-Benz U.S. International',
            LEGO._get_job('Lead, Farmer, Mercedes-Benz U.S. International')
    )) == 1
    # strips " at " if present on multi search
    assert len(re.findall(
            '^Lead Farmer at Mercedes-Benz U.S. International',
            LEGO._get_job('Lead, Farmer, at Mercedes-Benz U.S. International')
    )) == 1
    # strips whitespace
    assert len(re.findall(
            '^Lead Farmer at Mercedes-Benz U.S. International',
            LEGO._get_job(' Lead ,      Farmer   ,' +
                          '   at      Mercedes-Benz U.S. International')
    )) == 1
    # No match reply text
    assert len(
                re.findall(
                    '(No match for search term)',
                    LEGO._get_job('abcdxyz987321')
                    )
            ) == 1
    assert len(
                re.findall(
                    '(No match for search term)',
                    LEGO._get_job('Cosmetologist')
                    )
            ) == 0


@patch('Legobot.Lego.Lego.reply')
@patch('newjob.NewJob._get_job')
def test_handle_check(mock_get_job, mock_reply):
    msg = {'text': '!job developer', 'metadata': {'source_user': 'eugene'}}
    LEGO.handle(msg)

    mock_get_job.assert_called_once()
    mock_reply.assert_called_once()


BASEPLATE.stop()
