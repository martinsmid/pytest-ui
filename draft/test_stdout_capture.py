#!/usr/bin/env python
# encoding: utf-8

import sys
import unittest
from StringIO import StringIO


if __name__ == '__main__':
	_orig_stdout = sys.stdout
	_orig_stderr = sys.stderr
	sys.stdout = StringIO()
	sys.stderr = StringIO()

	loader = unittest.TestLoader()
	top_suite = loader.loadTestsFromName('test_module_b.test_feat_3')
	result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(top_suite)

	test_output = sys.stdout.getvalue()
	test_output_err = sys.stderr.getvalue()

	sys.stdout.close()
	sys.stderr.close()

	sys.stdout = _orig_stdout
	sys.stderr = _orig_stderr

	print 'And here is the output'
	print test_output
	print 'And here is the error output'
	print test_output_err