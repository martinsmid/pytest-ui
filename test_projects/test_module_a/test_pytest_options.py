import pytest
import unittest

class TestPytestOptions(unittest.TestCase):
    @pytest.mark.skip(reason="no way of currently testing this")
    def test_feat_1_case_1(self):
        raise Exception('This shouldn\'t run')

    @unittest.skip
    def test_unittest_skip(self):
        raise Exception('This shouldn\'t run')

    @pytest.mark.skip
    def test_pytest_skip(self):
        raise Exception('This shouldn\'t run')

    @pytest.mark.xfail
    def test_xfail(self):
        raise Exception('This shouldn\'t run IMHO')
