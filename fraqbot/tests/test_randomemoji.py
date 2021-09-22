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


from randomemoji import RandomEmoji  # noqa: E402


LOCK = threading.Lock()
BASEPLATE = Lego.start(None, LOCK)
LEGO = RandomEmoji(BASEPLATE, LOCK)


def test_listening_for():
    # !emoji
    assert LEGO.listening_for({'text': 'emoji'}) is False
    assert LEGO.listening_for({'text': '!emoji moin'}) is True
    assert LEGO.listening_for({'text': '!emoji 12'}) is True
    assert LEGO.listening_for({'text': '!Emoji'}) is False


def test_get_emoji():
    with patch('randomemoji.RandomEmoji._fetch_slack_emojis') as mocked_fse:
        mocked_fse.return_value = {'_man-shrugging': 'some_url'}
        assert isinstance(LEGO._get_emoji(5), str)
        assert len(re.findall(':[a-z0-9-_]+:', LEGO._get_emoji(1))) == 1
        assert len(re.findall(':[a-z0-9-_]+:', LEGO._get_emoji(5))) == 5
        assert len(re.findall(':[a-z0-9-_]+:', LEGO._get_emoji(20))) == 20
        assert len(re.findall(':[a-z0-9-_]+:', LEGO._get_emoji(5000))) == 20

        assert LEGO._get_emoji(1) == ':_man-shrugging:'

        five_long = ':_man-shrugging: :_man-shrugging:'
        + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:'
        assert LEGO._get_emoji(5) == five_long

        twenty_long = (':_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:')
        assert LEGO._get_emoji(20) == twenty_long
        assert LEGO._get_emoji(5000) == twenty_long


@patch('Legobot.Lego.Lego.reply')
@patch('randomemoji.RandomEmoji._get_emoji')
def test_handle_check(mock_get_emoji, mock_reply):
    msg = {'text': '!emoji 7', 'metadata': {'source_user': 'harold'}}
    LEGO.handle(msg)

    mock_get_emoji.assert_called_once()
    mock_reply.assert_called_once()


BASEPLATE.stop()
