#!/usr/bin/env python
# encoding: utf-8

import urwid
import logging
import unittest
from StringIO import StringIO

def result_state(test_result):
    if test_result.skipped:
        return 'skipped'
    elif test_result.failures:
        return 'failed'
    elif test_result.errors:
        return 'error'

    return 'x'

def get_tests(suite):
    test_list = {}
    for item in suite:
        if isinstance(item, unittest.suite.TestSuite):
            test_list.update(get_tests(item))
        else:
            test_list[item.id()] = item

    return test_list



def exit_program(button):
    raise urwid.ExitMainLoop()


class TestLine(urwid.Columns):

    def __init__(self, text):
        self._test_result = ' '

        self.w_text = urwid.Text(text)
        self.w_state = urwid.Text(u'[{}]'.format(self._test_result.upper()[0]))
        super(TestLine, self).__init__([self.w_text, self.w_state])

class TestLine2(urwid.Widget):
    _sizing = frozenset(['flow'])
    _selectable = True

    signals = ["click"]

    def __init__(self, test_id, *args, **kwargs):
        self.test_id = test_id
        self.test_result = ' '
        super(TestLine2, self).__init__(*args, **kwargs)

    def rows(self, size, focus=False):
        return 1

    def render(self, size, focus=False):
        (maxcol,) = size
        return urwid.TextCanvas(['{} [{}]'.format(self.test_id.ljust(maxcol - 4), self.test_result.upper()[0])], maxcol=maxcol)

    def keypress(self, size, key):
        if key == 'enter':
            self._emit('click')

        return key


class TestResultWindow(urwid.WidgetWrap):
    _sizing = frozenset(['box'])
    # _selectable = True

    def __init__(self, text, escape_method):
        self.escape_method = escape_method
        super(TestResultWindow, self).__init__(urwid.LineBox(urwid.Filler(urwid.Text(text))))

    def keypress(self, size, key):
        raise urwid.ExitMainLoop()
        if key == 'esc':
            self.escape_method()

        return None

class TestResultWindow2(urwid.LineBox):
    _sizing = frozenset(['box'])
    # _selectable = True

    def __init__(self, text, escape_method):
        self.escape_method = escape_method
        super(TestResultWindow2, self).__init__(urwid.Filler(urwid.Text(text)))

    def keypress(self, size, key):
        raise urwid.ExitMainLoop()
        if key == 'esc':
            self.escape_method()

        return key

class TestRunner(object):

    def __init__(self):
        urwid.set_encoding("UTF-8")
        loader = unittest.TestLoader()
        top_suite = loader.discover('.')
        self.tests = get_tests(top_suite)
        self.test_data = {}
        self.w_test_list = urwid.Padding(self.test_listbox(u'Python Urwid Test Runner', sorted(self.tests.keys())), left=2, right=2)
        self.w_main = self.w_test_list
        self.main_loop = None

    def run(self):
        self.main_loop = urwid.MainLoop(self.w_main, palette=[('reversed', 'standout', '')],
                       unhandled_input=self.unhandled_keypress)
        self.main_loop.run()

    def popup(self, widget):
        self._popup_original = self.main_loop.widget
        self.main_loop.widget = urwid.Overlay(
            widget,   
            self._popup_original,
            'left', ('relative', 80), 'top', ('relative', 80)
        )

    def _run_test(self, test_id):
        output = StringIO()
        suite = self.tests[test_id]
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
        result_state_str = result_state(result)
        self.test_data[test_id]['widget'].test_result = result_state_str
        self.test_data[test_id].update({
            'output': output.getvalue(),
            'result_state': result_state_str,
        })
        output.close()

    def _run_all_tests(self):
        for test_id, suite in self.tests.iteritems():
            self._run_test(test_id)

    def item_chosen(self, widget, choice):
        self.popup(
            TestResultWindow(self.test_data[choice]['output'], self.popup_close)
        )

    def popup_close(self):
        self.main_loop.widget = self._popup_original

    def test_listbox(self, title, choices):
        body = [urwid.Text(title), urwid.Divider()]
        for choice in choices:
            test_line = TestLine2(choice)
            self.test_data[choice] = {'widget': test_line}
            urwid.connect_signal(test_line, 'click', self.item_chosen, choice)
            body.append(urwid.AttrMap(test_line, None, focus_map='reversed'))
        return urwid.ListBox(urwid.SimpleFocusListWalker(body))

    def unhandled_keypress(self, key):
        if key in ('q', 'Q'):
            exit_program(None)
        elif key == 'r':
            self._run_all_tests()


if __name__ == '__main__':
    logging.basicConfig()
    runner = TestRunner()
    runner.run()
