#!/usr/bin/env python
# encoding: utf-8

import re
import sys
import urwid
import pytest
import logging
import traceback
import logging_tools
import thread
from collections import OrderedDict, defaultdict
import unittest
from StringIO import StringIO
import __builtin__

from plugin import PytestPlugin

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
        result_state_str = self.test_data.get('result_state', '')
        # logger.debug('rendering %s', self.test_data)
        (maxcol,) = size
        attr = []
        title_width = maxcol - 13
        main_attr = ('running', title_width) if self._is_running else (None, title_width)
        state_attr = (result_state_str, 10)
        return urwid.TextCanvas(['{} [{:10}]'.format(self.test_data['id'][:title_width].ljust(title_width), result_state_str[:10])],
            maxcol=maxcol, attr=[[main_attr, (None, 2), state_attr, (None, 1)]])

    def keypress(self, size, key):
        if key == 'enter':
            self._emit('click')

        return key


class StatusLine(urwid.Widget):
    _sizing = frozenset(['flow'])

    def __init__(self, runner, *args, **kwargs):
        super(StatusLine, self).__init__(*args, **kwargs)
        self.runner = runner

    def rows(self, size, focus=False):
        return 1

    def render(self, size, focus=False):
        (maxcol,) = size

        stats = self.runner.get_test_stats()
        return urwid.TextCanvas(
            ['Total: {} Filtered: {} Failed: {}'.format(stats['total'],
                                                        stats['filtered'],
                                                        stats['failed'])],
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

class Runner(object):
    def __init__(self, path='.', load_tests=True):
        self.ui = None
        self.path = path
        self.tests = OrderedDict()
        self.test_data = {}
        # self.rollbackImporter = RollbackImporter()

        if load_tests:
            self.init_tests()
            self.init_test_data()

    def set_test_result(self, test_id, result, output):
        logger.debug('result %s', result)
        # only update unset results to avoid overriding with teardown success
        test_data = self.test_data.get(test_id)
        if test_data and self.test_data[test_id].get('result') is None:
            self.test_data[test_id].update({
                'result': result,
                'output': output,
                'result_state': self.result_state(result)
            })

        self.ui.update_test_result(test_id)

    def clear_test_result(self, test_id):
        test_data = self.test_data.get(test_id)
        if test_data:
            self.test_data[test_id].update({
                'result': None,
                'output': '',
                'result_state': ''
            })

        self.ui.update_test_result(test_id)

    def set_exc_info(self, test_id, excinfo):
        self.test_data[test_id]['exc_info'] = excinfo
        self.test_data[test_id]['output'] = unicode(excinfo.getrepr())
        self.test_data[test_id]['result_state'] = 'failed'
        logger.debug('exc_info set: %s %s', test_id, self.test_data[test_id]['result_state'])

    def get_test_id(self, test):
        raise NotImplementedError()

    def is_test_failed(self, test):
        test_id = self.get_test_id(test)
        test_data = self.test_data.get(test_id)

        failed = not test_data or test_data.get('result_state') in self._test_fail_states
        logger.debug('failed: %r %s', failed, test_id)
        return failed

    def is_test_filtered(self, test):
        if not self.ui:
            return True

        return self.get_test_id(test) in self.ui.current_test_list.keys()

    def get_test_stats(self):
        res = {
            'total': 0,
            'filtered': 0,
            'failed': 0
        }
        for test_id, test in self.tests.iteritems():
            res['total'] += 1
            if self.test_data[test_id].get('result_state') in self._test_fail_states:
                res['failed'] += 1

            if self.is_test_filtered(test):
                res['filtered'] += 1

        return res

    def _get_tests(self, failed_only=True, filtered=True):
        tests = self.ui.current_test_list if filtered else self.tests

        return OrderedDict([(test_id, test) for test_id, test in tests.iteritems()
                                  if not failed_only
                                      or (failed_only and self.is_test_failed(test))])


class UnittestRunner(Runner):
    def get_test_id(self, test):
        return test.id()

    def init_tests(self):
        loader = unittest.TestLoader()
        top_suite = loader.discover(self.path)
        self.tests = get_tests(top_suite)

    def init_test_data(self):
        self.test_data = {test_id: {'suite': test} for test_id, test in self.tests.iteritems()}
        logger.debug('Inited tests %s', self.test_data)

    def reload_tests(self):
        if self.rollbackImporter:
            self.rollbackImporter.uninstall()
        self.rollbackImporter = RollbackImporter()
        self.init_tests()

    def run_tests(self, failed_only=True, filtered=True):
        self.reload_tests()
        tests = self._get_tests(failed_only, filtered)

        for test_id, suite in tests.iteritems():
            self._run_test(test_id)

    def result_state(self, test_result):
        if not test_result:
            return ''
        elif test_result.skipped:
            return 'skipped'
        elif test_result.failures:
            return 'failed'
        elif test_result.errors:
            return 'error'

        return 'ok'


class PytestRunner(Runner):
    _test_fail_states = ['failed', 'error', None, '']

    def get_test_id(self, test):
        return test.nodeid #.replace('/', '.')

    def init_tests(self):
        pytest.main(['--capture', 'sys', '-p', 'no:terminal', '--collect-only', self.path], plugins=[PytestPlugin(None, self)])

    def init_test_data(self):
        self.test_data = {test_id: {'suite': test} for test_id, test in self.tests.iteritems()}
        logger.debug('Inited tests %s', self.test_data)

    def add_test(self, item):
        self.tests[self.get_test_id(item)] = item

    def invalidate_test_results(self, tests):
        for test_id, test in tests.iteritems():
            self.clear_test_result(test_id)

    def run_tests(self, failed_only=True, filtered=True):
        self._running_tests = True
        tests = self._get_tests(failed_only, filtered)
        self.invalidate_test_results(tests)
        pytest.main(['--capture', 'sys', '-p', 'no:terminal', self.path],
            plugins=[PytestPlugin(None, self, self._get_tests(failed_only, filtered))])
        self._running_tests = False

    def result_state(self, report):
        if not report:
            return ''
        elif report.outcome == 'passed':
            return 'ok'
        elif report.outcome == 'failed':
            return 'failed'
        elif report.outcome == 'skipped':
            return 'skipped'

        logger.warn('Unknown report outcome %s', report.outcome)
        return 'N/A'

    def get_failed_sibling(self, test_id, direction):
        tests = self._get_tests(True, True)
        keys = tests.keys()
        try:
            next_pos = keys.index(test_id) + direction
        except ValueError as e:
            return None

        if not (next_pos >= 0 and next_pos < len(keys)):
            return None

        return keys[next_pos]

    def get_next_failed(self, test_id):
        return self.get_failed_sibling(test_id, 1)

    def get_previous_failed(self, test_id):
        return self.get_failed_sibling(test_id, -1)


class TestRunnerUI(object):
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

    def __init__(self, runner):
        logger.info('Runner UI init')
        urwid.set_encoding("UTF-8")

        self.main_loop = None
        self.w_main = None
        self.test_data = defaultdict(dict)
        self.re_filter = None
        self.runner = runner
        self.runner.ui = self
        self._first_failed_focused = False

        self.init_main_screen()
        self._running_tests = False
        self.init_test_listbox()

    def add_test(self, item):
        if item.nodeid in self.tests:
            logging.warn('Duplicate test id collected %s', item.nodeid)

        self.tests[item.nodeid] = item

    def init_main_screen(self):
        self.w_filter_edit = urwid.Edit('Filter ')
        aw_filter_edit = urwid.AttrMap(self.w_filter_edit, 'edit', 'edit_focus')
        self.w_status_line = urwid.AttrMap(StatusLine(self.runner), 'statusline', '')
        urwid.connect_signal(self.w_filter_edit, 'change', self.on_filter_change)
        self.init_test_listbox()
        self.w_main = urwid.Padding(
            urwid.Pile([
                ('pack', urwid.Text(u'Python Urwid Test Runner', align='center')),
                ('pack', urwid.Divider()),
                ('pack', aw_filter_edit),
                ('pack', urwid.Divider()),
                self.w_test_listbox,
                ('pack', urwid.Divider()),
                ('pack', self.w_status_line),
            ]),
            left=2, right=2
        )

    # def on_testlist_change(self):
    #     self.init_test_listbox()

    def init_test_listbox(self):
        self.w_test_listbox = self.test_listbox(self.current_test_list.keys())
        if self.w_main:
            self.w_main.original_widget.widget_list[4] = self.w_test_listbox
            self.w_main.original_widget._invalidate()

    @property
    def current_test_list(self):
        if not self.re_filter:
            return self.runner.tests

        current_test_list = OrderedDict([(k, v) for k, v in self.runner.tests.iteritems() if self.re_filter.findall(k)])
        return current_test_list

    def on_filter_change(self, filter_widget, filter_value):
        if not filter_value:
            self.re_filter = None
        else:
            regexp_str = '.*?'.join(list(iter(
                filter_value.replace('.', '\.').replace(r'\\', '\\\\')
            )))
            self.re_filter = re.compile(regexp_str, re.UNICODE + re.IGNORECASE)

        self.init_test_listbox()
        self.w_main.original_widget._invalidate()
        self.w_status_line.original_widget._invalidate()
        # self.main_loop.widget._invalidate()
        # self.main_loop.draw_screen()

    def run(self):
        self.main_loop = urwid.MainLoop(self.w_main, palette=self.palette,
                       unhandled_input=self.unhandled_keypress)
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

    def run_tests(self, failed_only=True, filtered=True):
        logger.info('Running tests (failed_only: %r, filtered: %r)', failed_only, filtered)
        self._running_tests = True
        self._first_failed_focused = False
        self.runner.run_tests(failed_only, filtered)

        self.w_test_listbox._invalidate()
        self.w_main._invalidate()
        self.main_loop.draw_screen()
        self._running_tests = False


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
        self.runner.set_test_result(test_id, result, sys.stdout.getvalue())

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

    def update_test_result(self, test_id):
        test_data = self.runner.test_data[test_id]
        result_state_str = test_data.get('result_state', '')
        logger.debug('test_data %s', test_data)
        self.test_data[test_id]['result_state'] = result_state_str
        if result_state_str in ['failed', 'error'] and not self._first_failed_focused:
            self.w_test_listbox.set_focus(self._get_test_position(test_id))
            self._first_failed_focused = True

        self.test_data[test_id]['widget']._invalidate()
        self.test_data[test_id]['lw_widget']._invalidate()
        # self.w_test_listbox._invalidate()
        self.w_status_line.original_widget._invalidate()

        self.main_loop.draw_screen()

    def show_test_detail(self, widget, test_id):
        test_data = self.runner.test_data[test_id]
        # if test has already been run
        if 'output' in test_data:
            output = test_data['output']
        if 'exc_info' in test_data:
            output += '\n' + '-'*20 + '\n'
            output += '\n'.join(traceback.format_tb(test_data['exc_info'].tb))

            result_window = TestResultWindow(
                output,
                self.popup_close)
            self.popup(result_window)
            result_window.set_focus(0)

    def popup_close(self):
        self.main_loop.widget = self._popup_original

    def get_list_item(self, test_id, position):
        result_state_str = self.runner.test_data[test_id].get('result_state', '')
        self.test_data[test_id].update({
            'widget': None,
            'lw_widget': None,
            'position': position,
            'id': test_id,
            'result_state': result_state_str
        })
        test_line = TestLine(self.test_data[test_id])
        self.test_data[test_id]['widget'] = test_line
        urwid.connect_signal(test_line, 'click', self.show_test_detail, test_id)
        test_line_attr = urwid.AttrMap(test_line, None, focus_map='reversed')
        self.test_data[test_id]['lw_widget'] = test_line_attr
        return test_line_attr

    def test_listbox(self, test_list):
        list_items = []
        for position, test_id in enumerate(test_list):
            test_line_attr = self.get_list_item(test_id, position)
            list_items.append(test_line_attr)
        return urwid.ListBox(urwid.SimpleFocusListWalker(list_items))

    def focus_failed_sibling(self, direction):
        tests = self.runner._get_tests(False, True)
        test_id = tests.keys()[self.w_test_listbox.focus_position]
        next_id = self.runner.get_failed_sibling(test_id, direction)
        if next_id is not None:
            next_pos = self._get_test_position(next_id)
            self.w_test_listbox.set_focus(next_pos, 'above' if direction == 1 else 'below')
            self.w_test_listbox._invalidate()

    def unhandled_keypress(self, key):
        if key in ('q', 'Q'):
            exit_program(None)
        elif key == '/':
            self.w_main.original_widget.set_focus(2)
        elif key == 'ctrl f':
            self.w_filter_edit.set_edit_text('')
            self.w_main.original_widget.set_focus(2)
        elif key == 'R':
            if not self._running_tests:
                thread.start_new_thread(
                    self.run_tests, (False, )
                )
        elif key == 'r' or key == 'f5':
            if not self._running_tests:
                thread.start_new_thread(
                    self.run_tests, (True, )
                )
        elif key == 'meta down':
            self.focus_failed_sibling(1)

        elif key == 'meta up':
            self.focus_failed_sibling(-1)


def main():
    path = sys.argv[1] if len(sys.argv) - 1 else '.'
    logging_tools.configure()
    logger.info('Configured logging')

    runner = PytestRunner(path)
    ui = TestRunnerUI(runner)
    ui.run()


if __name__ == '__main__':
    main()
