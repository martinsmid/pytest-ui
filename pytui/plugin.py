import logging_tools
from common import get_filter_regex


logger = logging_tools.get_logger(__name__)


def pytest_configure(config):
    """Activate the plugin."""

    if config.getvalue('pytui'):
        runner = PytestRunner('.') # TODO: get path, if needed
        plugin = PytestPlugin(config, runner)

        config.pluginmanager.register(plugin, '_pytui')


class PytestPlugin(object):
    def __init__(self, runner, filter_value=None, config=None):
        self.runner = runner
        self.filter_regex = get_filter_regex(filter_value)

    def pytest_runtest_protocol(self, item, nextitem):
        logger.debug('pytest_runtest_protocol %s %s', item, nextitem)

    def pytest_itemcollected(self, item):
        logger.debug('pytest_itemcollected %s', item)
        self.runner.item_collected(item)

    def pytest_runtest_makereport(self, item, call):
        logger.debug('pytest_runtest_makereport %s %s %s', item, call.when, str(type(call.excinfo)))
        if call.excinfo:
            self.runner.set_exception_info(item.nodeid, call.excinfo, call.when)

    def pytest_runtest_logreport(self, report):
        logger.debug('pytest_runtest_logreport %s', report)
        self.runner.set_test_result(
            report.nodeid,
            report,
            getattr(report, 'capstdout', '') + getattr(report, 'capstderr', '')
        )

    def pytest_collectreport(self, report):
        logger.debug('pytest_collectreport %s', report)

    def pytest_collection_modifyitems(self, session, config, items):
        # logger.debug('pytest_collection_modifyitems %s %s %s', session, config, items)
        def is_filtered(item):
            return self.filter_regex.findall(self.runner.get_test_id(item))

        if self.filter_regex:
            items[:] = filter(is_filtered, items)

