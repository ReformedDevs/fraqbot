import os
import pytest
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
        assert isinstance(LEGO._get_emoji(5, None), str)
        assert len(re.findall(':[a-z0-9-_]+:', LEGO._get_emoji(1, None))) == 1
        assert len(re.findall(':[a-z0-9-_]+:', LEGO._get_emoji(5, None))) == 5
        assert len(
            re.findall(':[a-z0-9-_]+:', LEGO._get_emoji(20, None))
        ) == 20
        assert len(
            re.findall(':[a-z0-9-_]+:', LEGO._get_emoji(5000, None))
        ) == 20

        assert LEGO._get_emoji(1, None) == ':_man-shrugging:'

        five_long = (':_man-shrugging: :_man-shrugging: '
                     + ':_man-shrugging: :_man-shrugging: :_man-shrugging:')
        assert LEGO._get_emoji(5, None) == five_long

        twenty_long = (':_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:'
                       + ' :_man-shrugging: :_man-shrugging: :_man-shrugging:')
        assert LEGO._get_emoji(20, None) == twenty_long
        assert LEGO._get_emoji(5000, None) == twenty_long

        # searching
        assert LEGO._get_emoji(1, '_man-') == ':_man-shrugging:'
        assert LEGO._get_emoji(1, 'rugg') == ':_man-shrugging:'
        assert LEGO._get_emoji(5, '_man-') == five_long
        assert len(
            re.findall('Nothing matched', LEGO._get_emoji(5, ' '))
        ) == 1
        assert len(
            re.findall('Nothing matched', LEGO._get_emoji(5, '__nomatch__'))
        ) == 1
        assert len(
            re.findall('_man-shrugging', LEGO._get_emoji(1, 'man'))
        ) == 1
        assert len(
            re.findall('_man-shrugging', LEGO._get_emoji(2, 'man'))
        ) == 2

        mocked_fse.return_value = {
            '_man-shrugging': 'some_url',
            '_woman-shrugging': 'some_url'
        }
        assert LEGO._get_emoji(1, 'woman') == ':_woman-shrugging:'
        assert len(
            re.findall('_woman-shrugging', LEGO._get_emoji(1, 'woman'))
        ) == 1

        # Find feature should only return the unique list
        assert LEGO._get_emoji(15, 'woman', True) == ':_woman-shrugging:'

        # emoji talk
        assert LEGO._get_emoji_talk(
            'something'
        ) == ':s::o::m::e::t::h::i::n::g:'
        assert LEGO._get_emoji_talk(
            'some 123 thing'
        ) == ':s::o::m::e::blank::one::two::three::blank::t::h::i::n::g:'
        # size limit
        assert LEGO._get_emoji_talk(
            ('something really long like this and longer'
             + ' than the allowance for emoji talk')
        ) == (':s::o::m::e::t::h::i::n::g::blank::r::e::a::l::l::y::blank::l:'
              + ':o::n::g::blank::l::i::k::e::blank::t::h::i::s::blank:'
              + ':a::n::d::blank::l::o::n::g::e::r:'
              + ':blank::t::h::a::n::blank::t::h:e allowan'
              + 'ce for emoji talk')


# !emoji 7
@patch('Legobot.Lego.Lego.reply')
@patch('randomemoji.RandomEmoji._get_emoji')
def test_handle_check(mock_get_emoji, mock_reply):
    msg = {'text': '!emoji 7', 'metadata': {'source_user': 'harold'}}
    LEGO.handle(msg)

    mock_get_emoji.assert_called_once()
    mock_reply.assert_called_once()


# !emoji
@patch('Legobot.Lego.Lego.reply')
@patch('randomemoji.RandomEmoji._get_emoji')
def test_handle_check_2(mock_get_emoji, mock_reply):
    msg = {'text': '!emoji', 'metadata': {'source_user': 'harold'}}
    LEGO.handle(msg)

    mock_get_emoji.assert_called_once()
    mock_reply.assert_called_once()


# !emoji bob
@patch('Legobot.Lego.Lego.reply')
@patch('randomemoji.RandomEmoji._get_emoji')
def test_handle_check_3(mock_get_emoji, mock_reply):
    msg = {'text': '!emoji bob', 'metadata': {'source_user': 'harold'}}
    LEGO.handle(msg)

    # Make sure get_emoji was not called
    with pytest.raises(AssertionError):
        mock_get_emoji.assert_called_once()
    mock_reply.assert_called_once()


@patch('Legobot.Lego.Lego.reply')
@patch('randomemoji.RandomEmoji.get_help')
@patch('randomemoji.RandomEmoji._get_emoji')
def test_get_help(mock_get_emoji, mock_get_help, mock_reply):
    msg = {'text': '!emoji help', 'metadata': {'source_user': 'harold'}}
    LEGO.handle(msg)

    # Make sure get_emoji was not called
    with pytest.raises(AssertionError):
        mock_get_emoji.assert_called_once()
    # Make sure get_help and reply were called
    mock_get_help.assert_called_once()
    mock_reply.assert_called_once()


BASEPLATE.stop()
