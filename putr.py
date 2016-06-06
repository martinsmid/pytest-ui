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
        for c in choices:
            button = urwid.Button(c)
            urwid.connect_signal(button, 'click', self.item_chosen, c)
            body.append(urwid.AttrMap(button, None, focus_map='reversed'))
        return urwid.ListBox(urwid.SimpleFocusListWalker(body))


if __name__ == '__main__':
    logging.basicConfig()
    runner = TestRunner()
    runner.run()
