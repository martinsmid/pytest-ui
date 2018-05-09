from __future__ import unicode_literals
import sys
import pytest
import logging
import tempfile
from unittest import mock, TestCase

from pytui.runner import PytestRunner


logger = logging.getLogger(__name__)
logging.basicConfig()
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

