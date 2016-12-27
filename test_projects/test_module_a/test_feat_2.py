import unittest


class TestD(unittest.TestCase):
    def test_feat_1_case_1(self):
        pass

    def test_feat_1_case_2(self):
        pass

    @unittest.skip
    def test_feat_1_case_3(self):
        pass

    def test_feat_1_case_4(self):
        pass
