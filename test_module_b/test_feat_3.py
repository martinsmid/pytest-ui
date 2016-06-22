import unittest
import time

class TestE(unittest.TestCase):
    def test_many_lines(self):
    	for i in xrange(100):
    		print 'Many lines', i

    def test_feat_1_case_1(self):
        time.sleep(0.5)

    def test_feat_1_case_2(self):
        time.sleep(0.5)

    def test_feat_1_case_3(self):
        time.sleep(0.5)

    def test_feat_1_case_4(self):
        for i in xrange(10):
            time.sleep(0.1)
            print 'Few lines %d' % i
