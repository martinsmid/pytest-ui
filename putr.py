#!/usr/bin/env python
# encoding: utf-8

import urwid
import logging
import unittest
from StringIO import StringIO

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

def handle_input(key):
    if key in ('q', 'Q'):
        exit_program(None)

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
        self.test_result = 'X'
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

class TestRunner(object):

    def __init__(self):
        loader = unittest.TestLoader()
        top_suite = loader.discover('.')
        self.tests = get_tests(top_suite)
        self.w_main = urwid.Padding(self.menu(u'Python Urwid Test Runner', sorted(self.tests.keys())), left=2, right=2)

    def run(self):
        urwid.MainLoop(self.w_main, palette=[('reversed', 'standout', '')],
                       unhandled_input=handle_input).run()

    def item_chosen(self, button, choice):
        output = StringIO()
        unittest.TextTestRunner(stream=output, verbosity=2).run(self.tests[choice])
        self.w_main.original_widget = urwid.Filler(urwid.Text(output.getvalue()))
        output.close()

    def menu(self, title, choices):
        body = [urwid.Text(title), urwid.Divider()]
        for choice in choices:
            button = TestLine2(choice)
            urwid.connect_signal(button, 'click', self.item_chosen, choice)
            body.append(urwid.AttrMap(button, None, focus_map='reversed'))
        return urwid.ListBox(urwid.SimpleFocusListWalker(body))


if __name__ == '__main__':
    logging.basicConfig()
    runner = TestRunner()
    runner.run()
