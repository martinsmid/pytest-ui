from __future__ import absolute_import
from __future__ import unicode_literals

import pytest
from unittest import TestCase
try:
    from unittest import mock
except ImportError:
    import mock
from pytui.common import get_filter_regex_str
from pytui.ui import Store

@pytest.mark.parametrize(
    'input,expected',
    [
        ('abc#efg', 'a.*?b.*?c.*efg'),
        ('abc#efg#ijkl', 'a.*?b.*?c.*efg.*i.*?j.*?k.*?l'),
        ('#efg#', '.*efg.*'),
    ]
)
def test_filter_regex_str(input, expected):
    regex = get_filter_regex_str(input)
    assert regex == expected


def test_fitler_match():
    store = Store(mock.Mock())
    store.is_test_failed = lambda x: True
    store.item_collected('test_1_abdefghij')
    store.item_collected('test_2_bheifhefe')
    store.item_collected('test_3_abefg')
    store.item_collected('test_4_axxbxxcefg')
    store.item_collected('test_5_axxbxxcxxefg')
    store.item_collected('test_6_axxbxxcxxexfg')

    store.set_filter('abc#efg')
    result = store._get_tests()
    assert dict(result) == {
        'test_4_axxbxxcefg': {
            'id': 'test_4_axxbxxcefg'
        },
        'test_5_axxbxxcxxefg': {
            'id': 'test_5_axxbxxcxxefg'
        },
    }

    store.set_filter('#xcx#')
    result = store._get_tests()
    assert dict(result) == {
        'test_5_axxbxxcxxefg': {
            'id': 'test_5_axxbxxcxxefg'
        },
        'test_6_axxbxxcxxexfg': {
            'id': 'test_6_axxbxxcxxexfg'
        }
    }
