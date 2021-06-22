from __future__ import absolute_import
from __future__ import unicode_literals
from future import standard_library
standard_library.install_aliases()

import mock
import pytest
import multiprocessing
from plugin import PytestPlugin
from functools import partial

import logging_tools
import runner

log_name = 'runner'
logger = logging_tools.get_logger(log_name)
pipe_logger = logging_tools.get_logger(log_name, 'pipe')
stdout_logger = logging_tools.get_logger(log_name, 'stdout')
stdout_logger_writer = logging_tools.LogWriter(stdout_logger)
stderr_logger = logging_tools.get_logger(log_name, 'stderr')
stderr_logger_writer = logging_tools.LogWriter(stderr_logger)


def process_run_tests():
    """ Class method as separate process entrypoint """

    # sys.stdout = stdout_logger_writer
    # sys.stderr = stderr_logger_writer

    # runner = cls(path, write_pipe=write_pipe, pipe_size=pipe_size,
    #              pipe_semaphore=pipe_semaphore)
    # exitcode, description = runner.run_tests(failed_only, filter_value)
    runner_mock = mock.Mock(get_test_id=partial(runner.PytestRunner.get_test_id, None))
    # runner_mock.get_test_id = mock.MagicMock(
    #     spec=runner.PytestRunner.get_test_id,
    #     side_effect=runner.PytestRunner.get_test_id
    # )
    exitcode = pytest.main(
        [
            '-s',
            # '-p', 'no:terminal',
            'test_projects/test_module_a/',
        ],
        plugins=[
            PytestPlugin(
                runner=runner_mock,
                filter_value='',
                select_tests='test_projects/test_module_a/test_feat_1.py'
                             '::TestOutputCapturing::test_feat_1_case_4'
            )
        ]
    )
    print(exitcode)
    # logger.info('Test run finished')
    # runner.pipe_send('run_finished')


def main():
    logging_tools.configure('pytui-runner.log', True)
    logger = logging_tools.get_logger('ui')
    logger.info('Configured logging')
    runner_process = multiprocessing.Process(
        target=process_run_tests,
        name='pytui-runner',
        args=()
    )
    runner_process.start()


if __name__ == '__main__':
    main()
