#!/usr/bin/env python
# encoding: utf-8

import re
import os
import sys
import json
import pytest
import logging
from _pytest.runner import Skipped
import traceback
from collections import OrderedDict
import unittest
from StringIO import StringIO

import logging_tools
from logging_tools import get_logger, LogWriter

from plugin import PytestPlugin


logger = get_logger(__name__)
pipe_logger = get_logger(__name__, 'pipe')
stdout_logger = get_logger(__name__, 'stdout')
stdout_logger_writer = LogWriter(stdout_logger)
stderr_logger = get_logger(__name__, 'stderr')
stderr_logger_writer = LogWriter(stderr_logger)
PIPE_LIMIT = 4096


def get_chunks(string):
    for offset in xrange(0, len(string), PIPE_LIMIT):
        yield string[offset:offset+PIPE_LIMIT]


class Runner(object):
    def __init__(self, path='.', write_pipe=None, pipe_size=None, pipe_semaphore=None):
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

        data_size = len(data)
        pipe_logger.debug('pipe write, data size: %s, pipe size: %s',
                          data_size, self.pipe_size.value)
        pipe_logger.debug('data: %s', data)

        for chunk in get_chunks(data):
            self.pipe_send_chunk(chunk)

    def pipe_send_chunk(self, chunk):
        chunk_size = len(chunk)
        # wait for pipe to empty
        while self.pipe_size.value + chunk_size > PIPE_LIMIT:
            pipe_logger.debug('no space in pipe: %d', self.pipe_size.value)
            pipe_logger.debug('waiting for reader')
            self.pipe_semaphore.clear()
            self.pipe_semaphore.wait()
            pipe_logger.debug('reader finished')

        with self.pipe_size.get_lock():
            self.pipe_size.value += chunk_size
            self.write_pipe.write(chunk)

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
            extracted_traceback = traceback.extract_tb(excinfo.tb)
        elif excinfo.type is Skipped:
            result = 'skipped'
            extracted_traceback = None
        else:
            result = 'failed'
            extracted_traceback = traceback.extract_tb(excinfo.tb)

        self.pipe_send('set_exception_info',
            test_id=test_id,
            exc_type=repr(excinfo.type),
            exc_value=traceback.format_exception_only(excinfo.type, excinfo.value)[-1],
            extracted_traceback=extracted_traceback,
            result_state=result,
            when=when
        )

    def get_test_id(self, test):
        raise NotImplementedError()


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
        """ Class method as separate process entrypoint """
        logging_tools.configure('pytui-runner.log')
        logger.info('Init started (path: %s)', path)

        sys.stdout = stdout_logger_writer
        sys.stderr = stderr_logger_writer

        runner = cls(path, write_pipe=write_pipe, pipe_size=pipe_size, pipe_semaphore=pipe_semaphore)
        runner.init_tests()

        logger.info('Init finished')

    @classmethod
    def process_run_tests(cls, path, failed_only, filtered, write_pipe,
                          pipe_size, pipe_semaphore, filter_value):
        """ Class method as separate process entrypoint """
        logging_tools.configure('pytui-runner.log')
        logger.info('Test run started (failed_only: %s, filtere: %s)', failed_only, filtered)

        sys.stdout = stdout_logger_writer
        # sys.stdout = sys.stderr = stdout_logger_writer
        sys.stderr = stderr_logger_writer

        runner = cls(path, write_pipe=write_pipe, pipe_size=pipe_size,
                     pipe_semaphore=pipe_semaphore)
        runner.run_tests(failed_only, filter_value)

        logger.info('Test run finished')

    def item_collected(self, item):
        # self.tests[self.get_test_id(item)] = item
        self.pipe_send('item_collected', item_id=self.get_test_id(item))

    def run_tests(self, failed_only, filter_value):
        args = ['-p', 'no:terminal', self.path]
        if failed_only:
            args.append('--lf')
        pytest.main(args,
            plugins=[PytestPlugin(runner=self, filter_value=filter_value)])

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

