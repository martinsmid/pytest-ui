from __future__ import unicode_literals

import sys
import pytest
import logging
import tempfile
try:
    from unittest import mock
except ImportError:
    import mock

from unittest import TestCase

from pytui.runner import PytestRunner, Runner


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


class PytestRunnerTests(TestCase):
    def setUp(self):
        self.pipe_mock = tempfile.TemporaryFile()
        self.pipe_size_mock = mock.Mock()
        self.pipe_semaphore_mock = mock.Mock()

    def test_skipping(self):
        runner = PytestRunner(
            'test_projects/test_module_a/',
            self.pipe_mock.fileno(),
            self.pipe_size_mock,
            self.pipe_semaphore_mock
        )
        with mock.patch.object(PytestRunner, 'pipe_send') as pipe_send_mock:
            logger.debug('------ runner init ------')
            runner.init_tests()
            # logger.debug(pipe_send_mock.call_args_list)
            logger.debug('------ runner run_tests ------')
            runner.run_tests(False, 'xfail')
            logger.debug(pipe_send_mock.call_args_list)

    @mock.patch.object(PytestRunner, 'init_tests', return_value=1)
    @mock.patch.object(Runner, 'pipe_send')
    def test_pytest_exitcode(self, pipe_send_mock, init_tests_mock):
        """
        Test whether set_init_fail(exitcode=1) is sent to ui from runner throught the pipe.
        """
        PytestRunner.process_init_tests(
            'test_projects/test_module_a/',
            self.pipe_mock.fileno(),
            self.pipe_size_mock,
            self.pipe_semaphore_mock
        )

        assert pipe_send_mock.call_args_list == [mock.call('set_init_fail', exitcode=1)]
