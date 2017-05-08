import unittest
import pytest

class TestFeatures(unittest.TestCase):
    def test_feat_1_case_1(self):
        pass

    def test_feat_1_case_2(self):
        pass

    @unittest.skip
    def test_unittest_skip(self):
        raise Exception('This shouldn\'t run')

    @pytest.mark.skip
    def test_pytest_skip(self):
        raise Exception('This shouldn\'t run')

    @pytest.mark.xfail
    def test_xfail(self):
        raise Exception('This shouldn\'t run IMHO')
