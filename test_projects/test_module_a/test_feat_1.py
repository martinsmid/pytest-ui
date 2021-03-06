from __future__ import print_function
import unittest

import logging

logging.basicConfig()
logger = logging.getLogger(__name__)

class TestOutputCapturing(unittest.TestCase):
    def test_feat_1_case_1(self):
        print('hello')
        logger.debug('hello at the debug level')

    def test_feat_1_case_2(self):
        self.assertEqual(True, False)

    def test_feat_1_case_3(self):
        logger.error('hello at the error level')

    def test_feat_1_case_4(self):
        pass
