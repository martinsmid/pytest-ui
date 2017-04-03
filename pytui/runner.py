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
    def __init__(self, path='.', write_pipe=None, pipe_size=None, pipe_semaphore=None):
        self.ui = None
        self.path = path
        self.tests = OrderedDict()
        logger.debug('%s Init', self.__class__.__name__)
        self.write_pipe = os.fdopen(write_pipe, 'w', 0)
        self.pipe_size = pipe_size
        self.pipe_semaphore = pipe_semaphore

    def pipe_send(self, method, **kwargs):
        data = '%s\n' % json.dumps({
                'method': method,
                'params': kwargs
        })
        pipe_lock = self.pipe_size.get_lock()
        data_size = len(data)
        # logger.debug('writing to pipe %s(%s)', method, kwargs)
        logger.debug('writing to pipe size: %s, pipe_size: %s',
                     data_size, self.pipe_size.value)
        # if the pipe would exceed 4000 bytes, wait for
        # the other end to consume
        # while self.pipe_size.value > 3500:
        #     pass

        if self.pipe_size.value + data_size > 400:
            self.pipe_semaphore.acquire()

        with pipe_lock:
            self.write_pipe.write(data)
            self.pipe_size.value += data_size

    def set_test_result(self, test_id, report, output):
        self.pipe_send('set_test_result',
            test_id=test_id,
            output=output,
            result_state=self.result_state(report),
            when=report.when,
            outcome=report.outcome
        )

    def set_exception_info(self, test_id, excinfo, when):
        exc_type, exc_value, exc_traceback = sys.exc_info()
        extracted_traceback = traceback.extract_tb(exc_traceback)
        self.pipe_send('set_exception_info',
            test_id=test_id,
            exc_type=exc_type,
            exc_value=exc_value,
            extracted_traceback=extracted_traceback,
            result='failed',
            when=when
        )

    def get_test_id(self, test):
        raise NotImplementedError()

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
    def process_init_tests(cls, path, write_pipe, pipe_size, pipe_semaphore):
        logging_tools.configure('pytui-runner.log')

        """ Class method for running in separate process """
        logger.debug('Inside the runner process %s %s %s' % (cls, path, write_pipe))
        runner = cls(path, write_pipe=write_pipe, pipe_size=pipe_size, pipe_semaphore=pipe_semaphore)
        runner.init_tests()
        logger.debug('Inside the runner process end')

    @classmethod
    def process_run_tests(cls, path, failed_only, filtered, write_pipe, pipe_size, pipe_semaphore):
        logging_tools.configure('pytui-runner.log')
        runner = cls(path, write_pipe=write_pipe, pipe_size=pipe_size, pipe_semaphore=pipe_semaphore)
        runner.run_tests(failed_only, filtered)

    def item_collected(self, item):
        # self.tests[self.get_test_id(item)] = item
        self.pipe_send('item_collected', item_id=self.get_test_id(item))

    def run_tests(self, failed_only, filtered):
        pytest.main(['-p', 'no:terminal', self.path],
            plugins=[PytestPlugin(runner=self)])

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
