#!/usr/bin/env python
# encoding: utf-8

from __future__ import absolute_import
from __future__ import unicode_literals
from future import standard_library
standard_library.install_aliases()
from builtins import range
from builtins import object

import re
import os
import sys
import json
import unittest
import traceback
from collections import OrderedDict
from io import StringIO


from tblib import Traceback
import pytest
from _pytest.runner import Skipped
import traceback

from . import logging_tools
from .logging_tools import get_logger, LogWriter
from .plugin import PytestPlugin
from .common import PytestExitcodes

log_name = 'runner'
logger = get_logger(log_name)
pipe_logger = get_logger(log_name, 'pipe')
stdout_logger = get_logger(log_name, 'stdout')
stdout_logger_writer = LogWriter(stdout_logger)
stderr_logger = get_logger(log_name, 'stderr')
stderr_logger_writer = LogWriter(stderr_logger)
PIPE_LIMIT = 4096


def get_chunks(string):
    for offset in range(0, len(string), PIPE_LIMIT):
        yield string[offset:offset+PIPE_LIMIT]


class Runner(object):
    def __init__(self, path='.', write_pipe=None, pipe_size=None, pipe_semaphore=None):
        self.path = path
        self.tests = OrderedDict()
        logger.debug('%s Init', self.__class__.__name__)
        self.write_pipe = os.fdopen(write_pipe, 'wb', 0)
        self.pipe_size = pipe_size
        self.pipe_semaphore = pipe_semaphore

    def pipe_send(self, method, **kwargs):
        data = bytes(b'%s\n' % json.dumps({
                'method': method,
                'params': kwargs
        }).encode('utf-8'))

        data_size = len(data)
        pipe_logger.debug('pipe write, data size: %s, pipe size: %s',
                          data_size, self.pipe_size.value)
        pipe_logger.debug('data: %s', data)

        for chunk in get_chunks(data):
            self.pipe_send_chunk(chunk)

    def pipe_send_chunk(self, chunk):
        chunk_size = len(chunk)
        # wait for pipe to empty
        # pipe_logger.debug('pipe_send_chunk')
        while True:
            # pipe_logger.debug('pipe check cycle')
            with self.pipe_size.get_lock():
                pipe_writable = self.pipe_size.value + chunk_size <= PIPE_LIMIT
                if pipe_writable:
                    pipe_logger.debug('pipe writable')
                    break

                pipe_logger.debug('no space in pipe: %d', self.pipe_size.value)
                pipe_logger.debug('  waiting for reader')
                self.pipe_semaphore.clear()
            self.pipe_semaphore.wait()
            pipe_logger.debug('  reader finished')

        with self.pipe_size.get_lock():
            self.pipe_size.value += chunk_size
            self.write_pipe.write(chunk)
            pipe_logger.debug('writing to pipe: %s', chunk)

    def set_test_result(self, test_id, report):
        output = \
            getattr(report, 'capstdout', '') + \
            getattr(report, 'capstderr', '')

        self.pipe_send('set_test_result',
            test_id=test_id,
            output=output,
            result_state=self.result_state(report),
            when=report.when,
            outcome=report.outcome
        )

    def set_test_state(self, test_id, state):
        self.pipe_send('set_test_state',
            test_id=test_id,
            state=state
        )

    def set_exception_info(self, test_id, excinfo, when, wasxfail, xfail_strict):
        if excinfo:
            logger.debug('exc info repr %s', excinfo._getreprcrash())
        elif wasxfail:
            if when == 'call':
                self.pipe_send('set_test_result',
                    test_id=test_id,
                    output='',
                    result_state='failed' if xfail_strict else 'xpass',
                    when=when,
                    outcome='passed',
                    last_failed_exempt=xfail_strict,
                )
                if xfail_strict:
                    logger.debug('LF EXEMPT %s', test_id)
            return
        if wasxfail:
            result = 'xfail'
            extracted_traceback = Traceback(excinfo.tb).to_dict()
        elif excinfo.type is Skipped:
            result = 'skipped'
            extracted_traceback = None
        else:
            result = 'failed'
            extracted_traceback = Traceback(excinfo.tb).to_dict()

        self.pipe_send(
            'set_exception_info',
            test_id=test_id,
            exc_type=repr(excinfo.type),
            exc_value=traceback.format_exception_only(excinfo.type, excinfo.value)[-1],
            extracted_traceback=extracted_traceback,
            result_state=result,
            when=when
        )

    def set_pytest_error(self, exitcode, description=None):
        self.pipe_send(
            'set_pytest_error',
            exitcode=exitcode,
            description=description
        )

    def get_test_id(self, test):
        raise NotImplementedError()


class PytestRunner(Runner):
    _test_fail_states = ['failed', 'error', None, '']

    def get_test_id(self, test):
        return test.nodeid #.replace('/', '.')

    def init_tests(self):
        logger.debug('Running pytest --collect-only')

        try:
            exitcode = pytest.main(['-p', 'no:terminal', '--collect-only', self.path],
                                   plugins=[PytestPlugin(runner=self)])
        except Exception as e:
            return PytestExitcodes.CRASHED, traceback.format_exc(e)

        return exitcode, None

    @classmethod
    def process_init_tests(cls, path, write_pipe, pipe_size, pipe_semaphore):
        """ Class method as separate process entrypoint """
        logging_tools.configure('pytui-runner.log')
        logger.info('Init started (path: %s)', path)

        sys.stdout = stdout_logger_writer
        sys.stderr = stderr_logger_writer

        runner = cls(path, write_pipe=write_pipe, pipe_size=pipe_size, pipe_semaphore=pipe_semaphore)
        exitcode, description = runner.init_tests()
        logger.warning('here, exitcode %d', exitcode)

        if exitcode != PytestExitcodes.ALL_COLLECTED:
            logger.warning('pytest failed with exitcode %d', exitcode)
            runner.set_pytest_error(exitcode, description)

        logger.info('Init finished')

    @classmethod
    def process_run_tests(cls, path, failed_only, filtered, write_pipe,
                          pipe_size, pipe_semaphore, filter_value):
        """ Class method as separate process entrypoint """
        logging_tools.configure('pytui-runner.log')
        logger.info('Test run started (failed_only: %s, filtered: %s)', failed_only, filtered)

        sys.stdout = stdout_logger_writer
        # sys.stdout = sys.stderr = stdout_logger_writer
        sys.stderr = stderr_logger_writer

        runner = cls(path, write_pipe=write_pipe, pipe_size=pipe_size,
                     pipe_semaphore=pipe_semaphore)
        exitcode, description = runner.run_tests(failed_only, filter_value)
        if exitcode in (PytestExitcodes.INTERNAL_ERROR,
                        PytestExitcodes.USAGE_ERROR,
                        PytestExitcodes.NO_TESTS_COLLECTED,
                        PytestExitcodes.CRASHED):
            logger.warning('pytest failed with exitcode %d', exitcode)
            runner.set_pytest_error(exitcode, description)

        logger.info('Test run finished')

    def item_collected(self, item):
        # self.tests[self.get_test_id(item)] = item
        self.pipe_send('item_collected', item_id=self.get_test_id(item))

    def run_tests(self, failed_only, filter_value):
        args = ['-p', 'no:terminal', self.path]
        if failed_only:
            args.append('--lf')

        try:
            exitcode = pytest.main(
                args,
                plugins=[PytestPlugin(runner=self, filter_value=filter_value)]
            )
        except Exception as e:
            return PytestExitcodes.CRASHED, traceback.format_exc(e)

        return exitcode, None

    def result_state(self, report):
        if not report:
            return ''
        elif report.outcome == 'passed':
            return 'ok'
        elif report.outcome == 'failed':
            return 'failed'
        elif report.outcome == 'skipped':
            return 'skipped'

        logger.warning('Unknown report outcome %s', report.outcome)
        return 'N/A'

