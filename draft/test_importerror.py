import sys
import pytest
import unittest
import logging
import logging_tools


logger = logging.getLogger(__name__)


class PutrPytestPlugin(object):
    def pytest_runtest_protocol(self, item, nextitem):
        print 'pytest_runtest_protocol %s %s' % (item, nextitem)

    def pytest_runtest_makereport(self, item, call):
        print 'pytest_runtest_makereport %s %s' % (item, call)

    # @pytest.hookimpl(hookwrapper=True)
    # def pytest_runtest_makereport(self, item, call):
    #     # logger.debug('pytest_runtest_makereport %s %s', item, call)
    #     outcome = yield
    #     # logger.debug('outcome %s', outcome)
    #     result = outcome.get_result()
    #     logger.debug('result %s', result)
    #     logger.debug('result.capstdout %s', result.capstdout)
    #     logger.debug('result.capstderr %s', result.capstderr)

    #     if call.when == 'call':
    #         self.runner.set_test_result(self.runner.get_test_id(item), call)

    #     logger.debug('pytest_runtest_makereport %s %s', item, call)

    def pytest_itemcollected(self, item):
        print 'pytest_itemcollected %s' % item

    def pytest_collectstart(self, collector):
        print 'pytest_collectstart(self, collector)'

    def pytest_collectreport(self, report):
        pass

    def pytest_runtest_logreport(self, report):
        print 'pytest_runtest_logreport'
        logger.debug('report %s', report)
        logger.debug('report.capstdout %s', report.capstdout)
        logger.debug('report.capstderr %s', report.capstderr)


if __name__ == '__main__':
    logging_tools.configure()

    print sys.path
    pytest.main(['-p', 'no:terminal', 'test_projects/test_module_a/test_feat_1.py'], plugins=[PutrPytestPlugin()])
