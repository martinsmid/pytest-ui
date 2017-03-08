#!/usr/bin/env python
# encoding: utf-8

import urwid

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
        print 'here'
        raise urwid.ExitMainLoop()
        if key == 'esc':
            self.escape_method()

        return key


class FixedLineBox(urwid.LineBox):
    _sizing = frozenset(['fixed'])

    def pack(self, size=None, focus=False):
        return (20, 2)


w_main = urwid.Overlay(
    TestResultWindow2('The\ntest\nresult', None),
    urwid.SolidFill(),
    'center', ('relative', 80), 'middle', ('relative', 80))


def handle_input(key):
    if key in ('q', 'Q'):
        print 'exiting on q'
        raise urwid.ExitMainLoop()
    elif key in ('1'):
        main_loop.widget = urwid.LineBox(urwid.Filler(urwid.Text('The second top window', align='right')))
        

if __name__ != '__main__':
    sys.exit(1)

main_loop = urwid.MainLoop(w_main, palette=[('reversed', 'standout', '')],
               unhandled_input=handle_input)
main_loop.run()
