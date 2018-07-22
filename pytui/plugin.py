from __future__ import absolute_import
from __future__ import unicode_literals
from builtins import str
from builtins import filter
from builtins import object

from . import logging_tools
from .common import get_filter_regex


logger = logging_tools.get_logger('runner.plugin')


class PytestPlugin(object):
    def __init__(self, runner, filter_value=None, config=None):
        self.runner = runner
        self.filter_regex = get_filter_regex(filter_value)
        logger.debug('plugin init %s %s', runner, filter_value)

    def pytest_runtest_protocol(self, item, nextitem):
        logger.debug('pytest_runtest_protocol %s %s', item.nodeid, nextitem)

    def pytest_collectreport(self, report):
        logger.debug('pytest_collectreport %s', report)

    def pytest_report_teststatus(self, report):
        logger.debug('pytest_report_teststatus %s', report)

    def pytest_runtest_setup(self, item):
        logger.debug('pytest_runtest_setup %s', item.nodeid)
        self.runner.set_test_state(
            item.nodeid,
            'setup'
        )

    def pytest_runtest_call(self, item):
        logger.debug('pytest_runtest_call %s', item.nodeid)
        self.runner.set_test_state(
            item.nodeid,
            'call'
        )

    def pytest_runtest_teardown(self, item):
        logger.debug('pytest_runtest_teardown %s', item.nodeid)
        self.runner.set_test_state(
            item.nodeid,
            'teardown'
        )

    def pytest_itemcollected(self, item):
        logger.debug('pytest_itemcollected %s', item.nodeid)
        self.runner.item_collected(item)

    def pytest_runtest_makereport(self, item, call):
        logger.debug('pytest_runtest_makereport %s %s %s', item.nodeid, call.when, str(call.excinfo))
        evalxfail = getattr(item, '_evalxfail', None)
        wasxfail = evalxfail and evalxfail.wasvalid() and evalxfail.istrue()
        if evalxfail:
            xfail_strict = evalxfail.get('strict', False)
            logger.debug('wasxfail: %s wasvalid: %s, istrue: %s, strict: %s',
                         wasxfail, evalxfail.wasvalid(), evalxfail.istrue(), xfail_strict)

        if call.excinfo:
            logger.debug('excinfo: %s reason: %s', call.excinfo, getattr(call.excinfo.value, 'msg', '-'))
            self.runner.set_exception_info(item.nodeid, call.excinfo, call.when, wasxfail, None)
        elif wasxfail and call.when == 'call':
            self.runner.set_exception_info(item.nodeid, None, call.when, wasxfail, xfail_strict)

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
            items[:] = list(filter(is_filtered, items))

        logger.debug('collect filtered  %s', [i.nodeid for i in items])

    def pytest_exception_interact(self, node, call, report):
        logger.debug('pytest_exception_interact %s %s %s', node.nodeid, call, report)
        self.runner.set_exception_info(node.nodeid, call.excinfo, call.when, False, None)

