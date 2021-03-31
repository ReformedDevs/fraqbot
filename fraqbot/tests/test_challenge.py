from Legobot.Lego import Lego
import os
import sys
import threading

LOCAL_PATH = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '..',
    'Local'
)
sys.path.append(LOCAL_PATH)
from challenge import Challenge  # noqa: E402

LOCK = threading.Lock()
BASEPLATE = Lego.start(None, LOCK)
LEGO = Challenge(BASEPLATE, LOCK)


def test_md_to_obj():
    # test no table in text
    assert LEGO._md_to_obj('test') is None

    # test no complete table in text (min 3 lines)
    assert LEGO._md_to_obj('a | b\n--- | ---') is None

    md = """Heading 1 | Heading 2 | Heading 3
--- | --- | ---
Item 1A | Item 2A | Item 3A
Item 1B | Item 2B | Item 3B"""
    correct = [
        {
            'Heading 1': 'Item 1A',
            'Heading 2': 'Item 2A',
            'Heading 3': 'Item 3A'
        },
        {
            'Heading 1': 'Item 1B',
            'Heading 2': 'Item 2B',
            'Heading 3': 'Item 3B'
        }
    ]
    assert LEGO._md_to_obj(md) == correct


def test_get_md_table():
    header = '### Leaderboard'

    # test no header in text
    assert LEGO._get_md_table('SOME TEXT\n', header) is None

    # test header exists but no table
    md = ('SOME TEXT\n\n### Leaderboard\n\n SOME MORE TEXT')
    assert LEGO._get_md_table(md, header) is None

    # test real data
    DIR = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(DIR, 'test.md')) as f:
        md = f.read()

    with open(os.path.join(DIR, 'correct_md_table.md')) as f:
        correct = f.read()

    assert LEGO._get_md_table(md, header) == correct


def test_obj_to_pretext():
    assert LEGO._obj_to_pretext('test') is None
    assert LEGO._obj_to_pretext([]) is None
    assert LEGO._obj_to_pretext(['test']) is None

    obj = [
        {
            'A Field': 'Value A 1',
            'B Field': 'Val b 1',
            'C': 'Value C1'
        },
        {
            'A Field': 'Val a2',
            'B Field': 'Value B 1',
            'C': 'Val C'
        }
    ]
    correct = '\n'.join([
        '  A Field  |  B Field  |    C     ',
        '----------------------------------',
        ' Value A 1 |  Val b 1  | Value C1 ',
        ' Val a2    | Value B 1 |    Val C '
    ])

    assert LEGO._obj_to_pretext(obj) == correct


def test_justify():
    cases = [
        {
            'text': 'HEADER',
            'length': 11,
            'dir': 'left',
            'pad': None,
            'correct': 'HEADER     '
        },
        {
            'text': 'HEADER',
            'length': 11,
            'dir': 'left',
            'pad': 1,
            'correct': ' HEADER    '
        },
        {
            'text': 'HEADER',
            'length': 11,
            'dir': 'center',
            'pad': None,
            'correct': '  HEADER   '
        },
        {
            'text': 'HEADER',
            'length': 11,
            'dir': 'center',
            'pad': 1,
            'correct': '  HEADER   '
        },
        {
            'text': 'HEADER',
            'length': 12,
            'dir': 'center',
            'pad': None,
            'correct': '   HEADER   '
        },
        {
            'text': 'HEADER',
            'length': 11,
            'dir': 'right',
            'pad': None,
            'correct': '     HEADER'
        },
        {
            'text': 'HEADER',
            'length': 11,
            'dir': 'right',
            'pad': 2,
            'correct': '   HEADER  '
        }
    ]

    for c in cases:
        r = LEGO._justify(c['text'], c['length'], c['dir'], c['pad'])
        assert r == c['correct']


BASEPLATE.stop()
