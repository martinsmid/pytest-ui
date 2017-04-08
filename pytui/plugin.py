import logging_tools

logger = logging_tools.get_logger(__name__)


def pytest_configure(config):
    """Activate the plugin."""

    if config.getvalue('pytui'):
        runner = PytestRunner('.') # TODO: get path, if needed
        plugin = PytestPlugin(config, runner)

        config.pluginmanager.register(plugin, '_pytui')


class PytestPlugin(object):
    def __init__(self, runner, config=None):
        self.runner = runner

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
        pass
        # logger.debug('pytest_collection_modifyitems %s %s %s', session, config, items)

        # items[:] = filter(self.runner.is_test_filtered, items)
        # logger.debug('Filtered items %s', items)

        # def filtered_and_failed(test):
        #     return self.runner.is_test_filtered(test) and self.runner.is_test_failed(test)

        # items[:] = filter(filtered_and_failed, items)
