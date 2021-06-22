from __future__ import unicode_literals
from builtins import object

import re
from .logging_tools import get_logger

logger = get_logger('ui')


def get_fuzzy_regex(fuzzy_str):
    return '.*?'.join(list(iter(
        fuzzy_str.replace('.', r'\.').replace(r'\\', '\\\\')
    )))


def get_filter_regex_str(filter_value):
    pieces = filter_value.split('#')
    return '.*'.join(
        (get_fuzzy_regex(value) if i % 2 == 0 else value
            for i, value in enumerate(pieces)
         )
    )


def get_filter_regex(filter_value):
    if not filter_value:
        return None

    regexp_str = get_filter_regex_str(filter_value)
    logger.debug('filter_regex %s', regexp_str)
    return re.compile(regexp_str, re.UNICODE + re.IGNORECASE)


class PytestExitcodes(object):
    ALL_COLLECTED = 0
    ALL_COLLECTED_SOME_FAILED = 1
    INTERRUPTED_BY_USER = 2
    INTERNAL_ERROR = 3
    USAGE_ERROR = 4
    NO_TESTS_COLLECTED = 5

    # Own exitcodes
    CRASHED = 100

    text = {
        ALL_COLLECTED: "All tests were collected and passed successfully",
        ALL_COLLECTED_SOME_FAILED: "Tests were collected and run but some of the tests failed",
        INTERRUPTED_BY_USER: "Test execution was interrupted by the user",
        INTERNAL_ERROR: "Internal error happened while executing tests",
        USAGE_ERROR: "pytest command line usage error",
        NO_TESTS_COLLECTED: "No tests were collected",
        CRASHED: "Pytest crashed",
    }
