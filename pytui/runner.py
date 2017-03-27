#!/usr/bin/env python
# encoding: utf-8

import re
import os
import sys
import json
import pytest
import logging
import traceback
import logging_tools
from collections import OrderedDict
import unittest
from StringIO import StringIO
import __builtin__

from plugin import PytestPlugin


logger = logging_tools.get_logger(__name__)


class RollbackImporter:
    def __init__(self):
        "Creates an instance and installs as the global importer"
        self.previousModules = sys.modules.copy()
        self.realImport = __builtin__.__import__
        __builtin__.__import__ = self._import
        self.newModules = {}

    def _import(self, name, globals=None, locals=None, fromlist=[], *args, **kwargs):
        # logger.debug('args: %s', args)
        # logger.debug('kwargs: %s', kwargs)
        result = apply(self.realImport, (name, globals, locals, fromlist))
        self.newModules[name] = 1
        return result

    def uninstall(self):
        logger.debug('uninstalling modules')
        for modname in self.newModules.keys():
            logger.debug('modname: %s', modname)
            if not self.previousModules.has_key(modname):
                # Force reload when modname next imported
                del(sys.modules[modname])
        __builtin__.__import__ = self.realImport


class Runner(object):
    def __init__(self, path='.', load_tests=True, write_pipe=None):
        self.ui = None
        self.path = path
        self.tests = OrderedDict()
        self.test_data = {}
        logger.debug('%s Init', self.__class__.__name__)
        self.write_pipe = os.fdopen(write_pipe, 'w', 0)
        if load_tests:
            self.init_tests()
            self.init_test_data()

    def set_test_result(self, test_id, result, output):
        logger.debug('result %s', result)
        # only update unset results to avoid overriding with teardown success
        test_data = self.test_data.get(test_id)
        if test_data and self.test_data[test_id].get('result') is None:
            self.test_data[test_id].update({
                'result': result,
                'output': output,
                'result_state': self.result_state(result)
            })

        self.update_test_result(test_id)

    def pipe_send(self, method, **kwargs):
        logger.debug('writing to pipe %s(%s)', method, kwargs)
        self.write_pipe.write('%s\n' % json.dumps({
                'method': method,
                'params': kwargs
            }))

    def update_test_result(self, test_id):
        # self.ui.update_test_result(test_id)
        self.pipe_send('update_test_result', test_id=test_id)

    def clear_test_result(self, test_id):
        test_data = self.test_data.get(test_id)
        if test_data:
            self.test_data[test_id].update({
                'result': None,
                'output': '',
                'result_state': ''
            })

        self.update_test_result(test_id)

    def set_exc_info(self, test_id, excinfo):
        self.test_data[test_id]['exc_info'] = excinfo
        self.test_data[test_id]['output'] = unicode(excinfo.getrepr())
        self.test_data[test_id]['result_state'] = 'failed'
        logger.debug('exc_info set: %s %s', test_id, self.test_data[test_id]['result_state'])

    def get_test_id(self, test):
        raise NotImplementedError()

    def is_test_failed(self, test):
        test_id = self.get_test_id(test)
        test_data = self.test_data.get(test_id)

        failed = not test_data or test_data.get('result_state') in self._test_fail_states
        logger.debug('failed: %r %s', failed, test_id)
        return failed

    def is_test_filtered(self, test):
        if not self.ui:
            return True

        return self.get_test_id(test) in self.ui.current_test_list.keys()

    def get_test_stats(self):
        res = {
            'total': 0,
            'filtered': 0,
            'failed': 0
        }
        for test_id, test in self.tests.iteritems():
            res['total'] += 1
            if self.test_data[test_id].get('result_state') in self._test_fail_states:
                res['failed'] += 1

            if self.is_test_filtered(test):
                res['filtered'] += 1

        return res

    def _get_tests(self, failed_only=True, filtered=True):
        tests = self.ui.current_test_list if filtered else self.tests

        return OrderedDict([(test_id, test) for test_id, test in tests.iteritems()
                                  if not failed_only
                                      or (failed_only and self.is_test_failed(test))])


class UnittestRunner(Runner):
    def get_suite_tests(suite):
        test_list = {}
        for item in suite:
            if isinstance(item, unittest.suite.TestSuite):
                test_list.update(self.get_suite_tests(item))
            else:
                test_list[item.id()] = item

        return OrderedDict(sorted(test_list.iteritems()))

    def get_test_id(self, test):
        return test.id()

    def init_tests(self):
        loader = unittest.TestLoader()
        top_suite = loader.discover(self.path)
        self.tests = self.get_suite_tests(top_suite)

    def init_test_data(self):
        self.test_data = {test_id: {'suite': test} for test_id, test in self.tests.iteritems()}
        logger.debug('Inited tests %s', self.test_data)

    def reload_tests(self):
        if self.rollbackImporter:
            self.rollbackImporter.uninstall()
        self.rollbackImporter = RollbackImporter()
        self.init_tests()

    def run_tests(self, failed_only=True, filtered=True):
        self.reload_tests()
        tests = self._get_tests(failed_only, filtered)

        for test_id, suite in tests.iteritems():
            self._run_test(test_id)

    def result_state(self, test_result):
        if not test_result:
            return ''
        elif test_result.skipped:
            return 'skipped'
        elif test_result.failures:
            return 'failed'
        elif test_result.errors:
            return 'error'

        return 'ok'


class PytestRunner(Runner):
    _test_fail_states = ['failed', 'error', None, '']

    def get_test_id(self, test):
        return test.nodeid #.replace('/', '.')

    def init_tests(self):
        logger.debug('Running pytest --collect-only')

        pytest.main(['-p', 'no:terminal', '--collect-only', self.path],
            plugins=[PytestPlugin(runner=self)])


    @classmethod
    def process_init_tests(cls, path, write_pipe):
        logging_tools.configure('pytui-runner.log')

        """ Class method for running in separate process """
        logger.debug('Inside the runner process %s %s %s' % (cls, path, write_pipe))
        runner = cls(path, write_pipe=write_pipe, load_tests=False)
        runner.init_tests()
        logger.debug('Inside the runner process end')

    @classmethod
    def process_run_tests(cls, failed_only, filtered):
        logging_tools.configure('pytui-runner.log')
        runner = cls(path, write_pipe=write_pipe, load_tests=False)
        runner.run_tests(failed_only, filtered)

    def init_test_data(self):
        self.test_data = {test_id: {'suite': test} for test_id, test in self.tests.iteritems()}
        logger.debug('Inited %d tests', len(self.test_data))

    def item_collected(self, item):
        # self.tests[self.get_test_id(item)] = item
        self.pipe_send('item_collected', item_id=self.get_test_id(item))

    def invalidate_test_results(self, tests):
        for test_id, test in tests.iteritems():
            self.clear_test_result(test_id)

    def run_tests(self, failed_only, filtered):
        self._running_tests = True
        tests = self._get_tests(failed_only, filtered)
        self.invalidate_test_results(tests)
        pytest.main(['-p', 'no:terminal', self.path],
            plugins=[PytestPlugin(runner=self)])
        self._running_tests = False

    def result_state(self, report):
        if not report:
            return ''
        elif report.outcome == 'passed':
            return 'ok'
        elif report.outcome == 'failed':
            return 'failed'
        elif report.outcome == 'skipped':
            return 'skipped'

        logger.warn('Unknown report outcome %s', report.outcome)
        return 'N/A'

    def get_failed_sibling(self, test_id, direction):
        tests = self._get_tests(True, True)
        keys = tests.keys()
        try:
            next_pos = keys.index(test_id) + direction
        except ValueError as e:
            return None

        if not (next_pos >= 0 and next_pos < len(keys)):
            return None

        return keys[next_pos]

    def get_next_failed(self, test_id):
        return self.get_failed_sibling(test_id, 1)

    def get_previous_failed(self, test_id):
        return self.get_failed_sibling(test_id, -1)
