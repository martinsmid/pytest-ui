import logging

logger = logging.getLogger(__name__)


def pytest_configure(config):
    """Activate the plugin."""

    if config.getvalue('pytui'):
        runner = PytestRunner('.') # TODO: get path, if needed
        plugin = PytestPlugin(config, runner)

        config.pluginmanager.register(plugin, '_pytui')


class PytestPlugin(object):
    def __init__(self, config, runner, test_list={}):
        self.runner = runner

    def pytest_runtest_protocol(self, item, nextitem):
        logger.debug('pytest_runtest_protocol %s %s', item, nextitem)

    def pytest_itemcollected(self, item):
        logger.debug('pytest_itemcollected %s', item)
        self.runner.add_test(item)

    def pytest_collectstart(self, collector):
        logger.debug('pytest_collectstart %s', collector)


    def pytest_runtest_makereport(self, item, call):
        logger.debug('pytest_runtest_makereport %s %s', item, str(type(call.excinfo)))
        if call.excinfo:
            self.runner.set_exc_info(item.nodeid, call.excinfo)

    def pytest_runtest_logreport(self, report):
        if (report.when == 'setup' and report.outcome == 'skipped'
            or report.when == 'call'):
            self.runner.set_test_result(report.nodeid, report, report.capstdout + report.capstderr)

    def pytest_collectreport(self, report):
        logger.debug('pytest_collectreport %s', report)

    def pytest_collection_modifyitems(self, session, config, items):
        logger.debug('pytest_collection_modifyitems %s %s %s', session, config, items)

        items[:] = filter(self.runner.is_test_filtered, items)
        logger.debug('Filtered items %s', items)
