import logging_tools
from common import get_filter_regex


logger = logging_tools.get_logger(__name__)


class PytestPlugin(object):
    def __init__(self, runner, filter_value=None, config=None):
        self.runner = runner
        self.filter_regex = get_filter_regex(filter_value)
        logger.debug('plugin init %s %s', runner, filter_value)

    def pytest_runtest_protocol(self, item, nextitem):
        logger.debug('pytest_runtest_protocol %s %s', item, nextitem)

    def pytest_collectreport(self, report):
        logger.debug('pytest_collectreport %s', report)

    def pytest_report_teststatus(self, report):
        logger.debug('pytest_report_teststatus %s', report)

    def pytest_runtest_setup(self, item):
        logger.debug('pytest_runtest_setup %s', item)
        self.runner.set_test_state(
            item.nodeid,
            'setup'
        )

    def pytest_runtest_call(self, item):
        logger.debug('pytest_runtest_call %s', item)
        self.runner.set_test_state(
            item.nodeid,
            'call'
        )

    def pytest_runtest_teardown(self, item):
        logger.debug('pytest_runtest_teardown %s', item)
        self.runner.set_test_state(
            item.nodeid,
            'teardown'
        )

    def pytest_itemcollected(self, item):
        logger.debug('pytest_itemcollected %s', item)
        self.runner.item_collected(item)

    def pytest_runtest_makereport(self, item, call):
        logger.debug('pytest_runtest_makereport %s %s %s', item, call.when, str(call.excinfo))
        evalxfail = getattr(item, '_evalxfail', None)
        # logger.debug('xfail %s', evalxfail.wasvalid())
        if evalxfail and evalxfail.wasvalid() and evalxfail.istrue():
            logger.debug('SKIPPED wasxfail %s, %s', evalxfail.getexplanation(), call.excinfo)
        import pytest
        # if call.skipped:
        if call.excinfo and call.excinfo.errisinstance(pytest.xfail.Exception):
            logger.debug('reason: %s', call.excinfo.value.msg)

        if call.excinfo:
            self.runner.set_exception_info(item.nodeid, call.excinfo, call.when)

    def pytest_runtest_logreport(self, report):
        logger.debug('pytest_runtest_logreport %s', report)
        self.runner.set_test_result(
            report.nodeid,
            report
        )

    def pytest_collectreport(self, report):
        logger.debug('pytest_collectreport %s', report)

    def pytest_collection_modifyitems(self, session, config, items):
        logger.debug('pytest_collection_modifyitems %s %s %s', session, config, items)
        def is_filtered(item):
            return self.filter_regex.findall(self.runner.get_test_id(item))

        # import pdb; pdb.set_trace()
        if self.filter_regex:
            items[:] = filter(is_filtered, items)

        logger.debug('collect filtered  %s', [i.nodeid for i in items])

