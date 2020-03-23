from __future__ import absolute_import
from __future__ import unicode_literals

from unittest import TestCase
from pytui.common import get_filter_regex_str


def test_filter_regex_str():
    regex = get_filter_regex_str('abc#efg')
    assert regex == 'a.*?b.*?cefg'