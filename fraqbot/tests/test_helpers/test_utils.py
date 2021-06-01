import os
import sys


HELPERS_DIR = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '..',
    '..',
    'Local',
    'helpers'
)
if HELPERS_DIR not in sys.path:
    sys.path.append(HELPERS_DIR)


import utils  # noqa: E402


def test_custom_function_key_val_to_fields():
    data = {'bob': 'tomato', 'larry': 'cucumber'}
    expected = [
        {'name': 'bob', 'type': 'tomato'},
        {'name': 'larry', 'type': 'cucumber'}
    ]
    result = utils.jsearch('key_val_to_fields(@, `name`, `type`)', data)
    assert result == expected


def test_custom_function_string_or_null():
    data = {
        'test_1': 'a string',
        'test_2': None,
        'test_3': 'None',
        'test_4': 'null',
        'test_5': 'none'
    }
    assert utils.jsearch('string_or_null(test_1)', data) == 'a string'
    assert utils.jsearch('string_or_null(test_2)', data) is None
    assert utils.jsearch('string_or_null(test_3)', data) is None
    assert utils.jsearch('string_or_null(test_4)', data) is None
    assert utils.jsearch('string_or_null(test_5)', data) == 'none'


def test_custom_functions_val_or_val():
    data = {
        'test_1': True,
        'test_2': False,
        'test_3': 'abc'
    }
    assert utils.jsearch('val_or_val(`1`, `2`, test_1)', data) == 1
    assert utils.jsearch('val_or_val(`1`, `2`, test_2)', data) == 2
    assert utils.jsearch('val_or_val(`1`, `2`, test_3 == `"abc"`)', data) == 1
    assert utils.jsearch('val_or_val(`1`, `2`, test_3 == `"xyz"`)', data) == 2


def test_set_properties():
    class TestClass(object):
        def __init__(self, properties):
            utils.set_properties(self, properties, __file__)

    property = {'name': 'my_prop', 'data': True}
    test = TestClass([property])
    assert test.my_prop is True

    property['file'] = {'path': '../data/test_json.json'}
    test = TestClass([property])
    assert test.my_prop == {'test': 'value'}

    property['file'] = {'path': '../data/test_json.json', 'raw': True}
    test = TestClass([property])
    assert test.my_prop == '{\n  "test": "value"\n}\n'
