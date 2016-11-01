#!/usr/bin/env python
# encoding: utf-8

import re
import sys
import urwid
import logging
import thread
from collections import OrderedDict
import unittest
from StringIO import StringIO

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


class TestLine(urwid.Columns):

    def __init__(self, text):
        self._test_result = ' '

        self.w_text = urwid.Text(text)
        self.w_state = urwid.Text(['[', (self._test_result, self._test_result.upper()[0]), ']'])
        super(TestLine, self).__init__([self.w_text, self.w_state])

class TestLine2(urwid.Widget):
    _sizing = frozenset(['flow'])
    _selectable = True

    signals = ["click"]

    def __init__(self, test_data, *args, **kwargs):
        self.test_data = test_data
        self._is_running = False
        super(TestLine2, self).__init__(*args, **kwargs)

    def rows(self, size, focus=False):
        return 1

    def render(self, size, focus=False):
        result_state_str = result_state(self.test_data.get('result'))
        test_id = self.test_data['suite'].id()
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


class TestResultWindow(urwid.WidgetWrap):
    _sizing = frozenset(['box', 'flow', 'fixed'])

    def __init__(self, text, escape_method):
        self.escape_method = escape_method
        super(TestResultWindow, self).__init__(urwid.LineBox(urwid.Filler(urwid.Text(text))))

    def keypress(self, size, key):
        if key == 'q':
            self.escape_method()

        return None

    def selectable(self):
        return True


class TestResultWindow2(urwid.LineBox):
    _sizing = frozenset(['box'])

    def __init__(self, text, escape_method):
        self.escape_method = escape_method
        super(TestResultWindow2, self).__init__(urwid.Filler(urwid.Text(text)))

    def keypress(self, size, key):
        if key == 'q':
            self.escape_method()

        return None

    def selectable(self):
        return True


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
    ]

    _test_fail_states = ['failed', 'error', None]

    def __init__(self):
        urwid.set_encoding("UTF-8")
        loader = unittest.TestLoader()
        top_suite = loader.discover('.')
        self.tests = get_tests(top_suite)
        self.test_data = {test_id: {'suite': test} for test_id, test in self.tests.iteritems()}
        self.current_test_list = self.tests
        self._init_main_screen()
        self.main_loop = None

    def _init_main_screen(self):
        self.w_filter_edit = urwid.AttrMap(urwid.Edit('Filter '), 'edit', 'edit_focus')
        urwid.connect_signal(self.w_filter_edit.original_widget, 'change', self.on_filter_change)
        self._init_test_listbox()
        self.w_main = urwid.Padding(
            urwid.Pile(
                [
                 ('pack', urwid.Text(u'Python Urwid Test Runner', align='center')),
                 ('pack', urwid.Divider()),
                 ('pack', self.w_filter_edit),
                 ('pack', urwid.Divider()),
                 self.w_test_listbox
                 ]
            ),
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
        self.main_loop.draw_screen()

    def _get_tests(self, failed_only=True, filtered=True):
        tests = self.current_test_list if filtered else self.tests

        return OrderedDict([(test_id, test) for test_id, test in tests.iteritems()
                                  if not failed_only
                                      or failed_only
                                      and self.test_data[test_id].get('result_state') in self._test_fail_states])

    def _run_tests(self, failed_only=True, filtered=True):
        self._first_failed_focused = False
        tests = self._get_tests(failed_only, filtered)

        for test_id, suite in tests.iteritems():
            self._run_test(test_id)

        self.w_test_listbox._invalidate()
        self.w_main._invalidate()
        self.main_loop.draw_screen()

    def show_test_detail(self, widget, choice):
        # if test has already been run
        if 'output' in self.test_data[choice]:
            self.popup(
                TestResultWindow2(self.test_data[choice]['output'], self.popup_close)
            )

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
            test_line = TestLine2(self.test_data[test_id])
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
            thread.start_new_thread(
                self._run_tests, (False, )
            )
        elif key == 'r':
            thread.start_new_thread(
                self._run_tests, (True, )
            )

    def set_test_list(self, test_list):
        self._test_list = test_list

if __name__ == '__main__':
    logging.basicConfig()
    runner = TestRunner()
    runner.run()
