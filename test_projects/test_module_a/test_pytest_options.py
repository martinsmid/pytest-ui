import pytest
import unittest

class TestPytestOptions(unittest.TestCase):
    @unittest.skip
    def test_unittest_skip(self):
        raise Exception('This shouldn\'t run')

    @pytest.mark.skip
    def test_pytest_skip(self):
        raise Exception('This shouldn\'t run')

    @pytest.mark.xfail(reason='This fails as expected (no strict)')
    def test_xfail_correct_easy(self):
        raise Exception('This is an expected failure')

    @pytest.mark.xfail(reason='''This should fail, but it doesn't, but nobody cares''')
    def test_xfail_wrong_easy(self):
        pass

    @pytest.mark.xfail(reason='This fails as expected (strict)', strict=True)
    def test_xfail_correct_strict(self):
        raise Exception('This is an expected failure')

    @pytest.mark.xfail(reason='''This should fail, but it doesn't. Pytest cares''', strict=True)
    def test_xfail_wrong_strict(self):
        pass
