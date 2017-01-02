#!/usr/bin/env python
# encoding: utf-8

import re
import sys
import urwid
import pytest
import logging
import logging_tools
import thread
from collections import OrderedDict
import unittest
from StringIO import StringIO
import __builtin__

logger = logging.getLogger(__name__)


class RollbackImporter:
    def __init__(self):
        "Creates an instance and installs as the global importer"
        self.previousModules = sys.modules.copy()
        self.realImport = __builtin__.__import__
        __builtin__.__import__ = self._import
        self.newModules = {}

    def _import(self, name, globals=None, locals=None, fromlist=[], *args, **kwargs):
        # logger.debug('args: %s', args)
        # logger.debug('kwargs: %s', kwargs)
        result = apply(self.realImport, (name, globals, locals, fromlist))
        self.newModules[name] = 1
        return result

    def uninstall(self):
        logger.debug('uninstalling modules')
        for modname in self.newModules.keys():
            logger.debug('modname: %s', modname)
            if not self.previousModules.has_key(modname):
                # Force reload when modname next imported
                del(sys.modules[modname])
        __builtin__.__import__ = self.realImport


def result_state(test_result):
    if not test_result:
        return ''

    if test_result.skipped:
        return 'skipped'
    elif test_result.failures:
        return 'failed'
    elif test_result.errors:
        return 'error'

    return 'ok'

def get_tests(suite):
    test_list = {}
    for item in suite:
        if isinstance(item, unittest.suite.TestSuite):
            test_list.update(get_tests(item))
        else:
            test_list[item.id()] = item

    return OrderedDict(sorted(test_list.iteritems()))

def exit_program(button):
    raise urwid.ExitMainLoop()


def get_test_id(test):
    if hasattr(test, 'id'):
        return test.id()
    elif hasattr(test, 'nodeid'):
        return test.nodeid.replace('/', '.')

class TestLine(urwid.Widget):
    _sizing = frozenset(['flow'])
    _selectable = True

    signals = ["click"]

    def __init__(self, test_data, *args, **kwargs):
        self.test_data = test_data
        self._is_running = False
        super(TestLine, self).__init__(*args, **kwargs)

    def rows(self, size, focus=False):
        return 1

    def render(self, size, focus=False):
        result_state_str = result_state(self.test_data.get('result'))
        test_id = get_test_id(self.test_data['suite'])
        (maxcol,) = size
        attr = []
        main_attr = ('running', maxcol - 13) if self._is_running else (None, maxcol - 13)
        state_attr = (result_state_str, 10)

        return urwid.TextCanvas(['{} [{:10}]'.format(test_id.ljust(maxcol - 13), result_state_str[:10])],
            maxcol=maxcol, attr=[[main_attr, (None, 2), state_attr, (None, 1)]])

    def keypress(self, size, key):
        if key == 'enter':
            self._emit('click')

        return key


class StatusLine(urwid.Widget):
    _sizing = frozenset(['flow'])

    def __init__(self, status, *args, **kwargs):
        super(StatusLine, self).__init__(*args, **kwargs)
        self.status = status

    def rows(self, size, focus=False):
        return 1

    def render(self, size, focus=False):
        (maxcol,) = size

        return urwid.TextCanvas(
            ['Total: {} Filtered: {} Failed: {}'.format(self.status.total,
                                                        self.status.filtered,
                                                        self.status.failed)],
            maxcol=maxcol)


class TestResultWindow(urwid.LineBox):
    _sizing = frozenset(['box'])

    def __init__(self, text, escape_method):
        self.escape_method = escape_method

        lines = text.split('\n')
        list_items = [
            urwid.AttrMap(urwid.Text(line), None, focus_map='reversed') for line in lines
        ]

        super(TestResultWindow, self).__init__(
            urwid.ListBox(
                urwid.SimpleFocusListWalker(list_items)
            )
        )

    def keypress(self, size, key):
        if key == 'q':
            self.escape_method()

        self._original_widget.keypress(size, key)

        return None

    def selectable(self):
        return True

    def set_focus(self, item):
        self._original_widget.set_focus(item)

class PutrPytestPlugin(object):
    def __init__(self, ui):
        self.ui = ui

    def pytest_runtest_protocol(self, item, nextitem):
        logger.debug('pytest_runtest_protocol %s %s', item, nextitem)

    def pytest_runtest_makereport(self, item, call):
        logger.debug('pytest_runtest_makereport %s %s', item, call)

    def pytest_itemcollected(self, item):
        logger.debug('pytest_itemcollected %s', item)
        self.ui.add_test(item)

    def pytest_collectstart(self, collector):
        logger.debug('pytest_collectstart %s', collector)


class TestRunner(object):
    palette = [
        ('reversed',    '',           'dark gray'),
        ('edit',        '',           'dark blue',    '', '',     '#008'),
        ('edit_focus',  '',           'light blue',   '', '',     '#00b'),
        ('failed',      'light red',  '',             '', '',     '#b00'),
        ('error',       'brown',      '',             '', '#f88', '#b00'),
        ('skipped',     'light gray', '',             '', '#f88', '#b00'),
        ('running',     'yellow',     'dark magenta',      '', '',     ''),
        ('ok',          'dark green', '',             '', '',     ''),
        ('statusline',  'white',      'dark blue',    '', '',     ''),
    ]

    _test_fail_states = ['failed', 'error', None]

    def __init__(self, path='.', load_tests=True, runner='pytest'):
        logger.info('Runner init')
        urwid.set_encoding("UTF-8")

        # self.rollbackImporter = RollbackImporter()
        self.current_test_list = {}
        self.tests = {}
        self.runner = runner
        self.path = path

        if load_tests:
            self.init_tests()
            self.init_test_data()

        self.init_main_screen()
        self.main_loop = None
        self._running_tests = False

    @property
    def filtered(self):
        return len(self.current_test_list)

    @property
    def total(self):
        return len(self.tests)

    @property
    def failed(self):
        return len(self._get_tests(failed_only=True))

    def init_tests(self):
        if self.runner == 'unittest':
            self.init_tests_unittest()
        elif self.runner == 'pytest':
            self.init_tests_pytest()

    def init_tests_unittest(self):
        loader = unittest.TestLoader()
        top_suite = loader.discover(self.path)
        self.tests = get_tests(top_suite)

    def init_tests_pytest(self):
        pytest.main(['-s', '--collect-only', self.path], plugins=[PutrPytestPlugin(self)])

    def init_test_data(self):
        self.test_data = {test_id: {'suite': test} for test_id, test in self.tests.iteritems()}
        self.current_test_list = self.tests
        logger.debug('Inited tests %s', self.test_data)
        self._init_test_listbox()

    def add_test(self, item):
        # import pdb; pdb.set_trace()
        if item.nodeid in self.tests:
            logging.warn('Duplicate test id collected %s', item.nodeid)

        self.tests[item.nodeid] = item

    def reload_tests(self):
        if self.rollbackImporter:
            self.rollbackImporter.uninstall()
        self.rollbackImporter = RollbackImporter()
        self.init_tests()

    def init_main_screen(self):
        self.w_filter_edit = urwid.AttrMap(urwid.Edit('Filter '), 'edit', 'edit_focus')
        self.w_status_line = urwid.AttrMap(StatusLine(self), 'statusline', '')
        urwid.connect_signal(self.w_filter_edit.original_widget, 'change', self.on_filter_change)
        self._init_test_listbox()
        self.w_main = urwid.Padding(
            urwid.Pile([
                ('pack', urwid.Text(u'Python Urwid Test Runner', align='center')),
                ('pack', urwid.Divider()),
                ('pack', self.w_filter_edit),
                ('pack', urwid.Divider()),
                self.w_test_listbox,
                ('pack', urwid.Divider()),
                ('pack', self.w_status_line),
            ]),
            left=2, right=2
        )

    def _init_test_listbox(self):
        self.w_test_listbox = self.test_listbox(self.current_test_list.keys())

    def on_filter_change(self, filter_widget, filter_value):
        regexp_str = '.*?'.join(list(iter(filter_value)))
        re_filter = re.compile(regexp_str, re.UNICODE + re.IGNORECASE)

        self.current_test_list = {k: v for k, v in self.tests.iteritems() if re_filter.findall(k)}
        self.w_main.original_widget.widget_list[4] = self.test_listbox(self.current_test_list.keys())
        self.w_main.original_widget._invalidate()
        self.w_status_line.original_widget._invalidate()
        # self.main_loop.widget._invalidate()
        # self.main_loop.draw_screen()

    def run(self):
        self.main_loop = urwid.MainLoop(self.w_main, palette=self.palette,
                       unhandled_input=self.unhandled_keypress)

        # self._run_tests()
        self.main_loop.run()

    def popup(self, widget):
        self._popup_original = self.main_loop.widget
        self.main_loop.widget = urwid.Overlay(
            widget,
            self._popup_original,
            'center', ('relative', 90), 'middle', ('relative', 90)
        )

    def _get_test_position(self, test_id):
        return self.test_data[test_id]['position']

    def _run_test(self, test_id):

        self.test_data[test_id]['widget']._is_running = True
        self.test_data[test_id]['widget']._invalidate()

        # self.w_test_listbox._invalidate()
        # self.w_main._invalidate()
        self.main_loop.draw_screen()

        _orig_stdout = sys.stdout
        _orig_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()

        suite = self.tests[test_id]
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
        self.test_data[test_id]['result'] = result
        result_state_str = result_state(result)
        if result_state_str in ['failed', 'error'] and not self._first_failed_focused:
            self.w_test_listbox.set_focus(self._get_test_position(test_id))
            self._first_failed_focused = True

        self.test_data[test_id].update({
            'output': sys.stdout.getvalue(),
            'result_state': result_state_str,
        })
        sys.stdout.close()
        sys.stderr.close()

        sys.stdout = _orig_stdout
        sys.stderr = _orig_stderr

        self.test_data[test_id]['widget']._is_running = False
        self.test_data[test_id]['widget']._invalidate()
        # self.w_test_listbox._invalidate()
        # self.w_main._invalidate()
        self.w_status_line.original_widget._invalidate()
        self.main_loop.draw_screen()

    def _get_tests(self, failed_only=True, filtered=True):
        tests = self.current_test_list if filtered else self.tests

        return OrderedDict([(test_id, test) for test_id, test in tests.iteritems()
                                  if not failed_only
                                      or failed_only
                                      and self.test_data[test_id].get('result_state') in self._test_fail_states])

    def _run_tests(self, failed_only=True, filtered=True):
        self._running_tests = True
        self.reload_tests()
        self._first_failed_focused = False
        tests = self._get_tests(failed_only, filtered)

        for test_id, suite in tests.iteritems():
            self._run_test(test_id)

        self.w_test_listbox._invalidate()
        self.w_main._invalidate()
        self.main_loop.draw_screen()
        self._running_tests = False

    def show_test_detail(self, widget, choice):
        # if test has already been run
        if 'output' in self.test_data[choice]:
            result_window = TestResultWindow(self.test_data[choice]['output'], self.popup_close)
            self.popup(result_window)
            result_window.set_focus(0)

    def popup_close(self):
        self.main_loop.widget = self._popup_original

    def test_listbox(self, test_list):
        list_items = []
        for position, test_id in enumerate(test_list):
            self.test_data[test_id].update({
                'id': test_id,
                'widget': None,
                'position': position,
            })
            test_line = TestLine(self.test_data[test_id])
            self.test_data[test_id]['widget'] = test_line
            urwid.connect_signal(test_line, 'click', self.show_test_detail, test_id)
            list_items.append(urwid.AttrMap(test_line, None, focus_map='reversed'))
        return urwid.ListBox(urwid.SimpleFocusListWalker(list_items))

    def unhandled_keypress(self, key):
        if key in ('q', 'Q'):
            exit_program(None)
        elif key == '/':
            self.w_main.original_widget.set_focus(2)
        elif key == 'R':
            if not self._running_tests:
                thread.start_new_thread(
                    self._run_tests, (False, )
                )
        elif key == 'r':
            if not self._running_tests:
                thread.start_new_thread(
                    self._run_tests, (True, )
                )

    def set_test_list(self, test_list):
        self._test_list = test_list

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) - 1 else '.'
    logging_tools.configure()
    logger.debug('Configured logging')
    runner = TestRunner(path, load_tests=True)
    runner.run()
