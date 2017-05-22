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

    @pytest.mark.xfail(reason='There is a bug somewhere')
    def test_xfail_correct_easy(self):
        raise Exception('This shouldn\'t run')

    @pytest.mark.xfail(reason='There is a bug somewhere (but it disappeared!)')
    def test_xfail_wrong_easy(self):
        pass

    @pytest.mark.xfail(reason='There is a bug somewhere', strict=True)
    def test_xfail_correct_strict(self):
        raise Exception('This shouldn\'t run')

    @pytest.mark.xfail(reason='There is a bug somewhere (but it disappeared!)', strict=True)
    def test_xfail_wrong_strict(self):
        pass
