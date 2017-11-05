# coding: utf-8
import unittest
import time

class TestE(unittest.TestCase):
    def test_many_lines(self):
    	for i in xrange(100):
    		print 'Many lines', i

    def test_feat_1_case_1(self):
        time.sleep(0.5)
        self.fail('Artificial fail one')

    def test_feat_1_case_2(self):
        time.sleep(0.5)
        self.fail('Artificial fail two')

    def test_feat_1_case_3(self):
        time.sleep(0.5)

    def test_feat_1_case_4(self):
        for i in xrange(10):
            time.sleep(0.1)
            print 'Few lines %d' % i

    def test_long_traceback(self):
        def recursive(n):
            if n == 0:
                raise Exception(u'\u1155\u1166'.encode('utf-8'))
            recursive(n-1)

        recursive(100)
