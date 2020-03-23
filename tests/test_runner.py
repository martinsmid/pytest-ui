from __future__ import unicode_literals
from __future__ import absolute_import

try:
    from unittest import mock
except ImportError:
    import mock
import logging
import tempfile

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
            exitcode, _description = runner.init_tests()
            assert exitcode == 0
            # logger.debug(pipe_send_mock.call_args_list)

            logger.debug('------ runner run_tests ------')
            exitcode, _description = runner.run_tests(False, 'xfail')
            assert exitcode == 1
            logger.debug(pipe_send_mock.call_args_list)

    @mock.patch.object(PytestRunner, 'init_tests', return_value=(1, None))
    @mock.patch.object(Runner, 'pipe_send')
    def test_pytest_exitcode(self, pipe_send_mock, init_tests_mock):
        """
        Test whether set_pytest_error(exitcode=1) is sent to ui from runner throught the pipe.
        """
        PytestRunner.process_init_tests(
            'test_projects/test_module_a/',
            self.pipe_mock.fileno(),
            self.pipe_size_mock,
            self.pipe_semaphore_mock,
            debug=True
        )

        assert pipe_send_mock.call_args_list == [
            mock.call('set_pytest_error', exitcode=1, description=None),
            mock.call('init_finished')
        ]
