#!/usr/bin/env python
# encoding: utf-8

import re
import json
import urwid
import thread
import logging
import multiprocessing
from collections import OrderedDict, defaultdict

import logging_tools
from runner import PytestRunner


logger = logging_tools.get_logger(__name__)


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

    def __init__(self, stats_callback, *args, **kwargs):
        super(StatusLine, self).__init__(*args, **kwargs)
        self.stats_callback = stats_callback

    def rows(self, size, focus=False):
        return 1

    def render(self, size, focus=False):
        (maxcol,) = size

        stats = self.stats_callback()
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

    def __init__(self, runner_class, path):
        logger.info('Runner UI init')
        urwid.set_encoding("UTF-8")

        self.runner_class = runner_class
        self.path = path
        self.test_data = OrderedDict()

        self.main_loop = None
        self.w_main = None
        self.filter_regex = None
        self.filter_value = None
        self._first_failed_focused = False
        self._running_tests = False
        self.child_pipe = None

        self.init_main_screen()

    def init_main_screen(self):
        self.w_filter_edit = urwid.Edit('Filter ')
        aw_filter_edit = urwid.AttrMap(self.w_filter_edit, 'edit', 'edit_focus')
        self.w_status_line = urwid.AttrMap(StatusLine(self.get_test_stats), 'statusline', '')
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

    def init_test_listbox(self):
        self.w_test_listbox = self.test_listbox(self.current_test_list.keys())
        if self.w_main:
            self.w_status_line.original_widget._invalidate()
            self.w_main.original_widget.widget_list[4] = self.w_test_listbox
            self.w_main.original_widget._invalidate()

    def init_test_data(self):
        multiprocessing.Process(
            target=self.runner_class.process_init_tests,
            args=(self.path, self.child_pipe)
        ).start()

    @property
    def current_test_list(self):
        if not self.filter_regex:
            return self.test_data

        current_test_list = OrderedDict([
            (k, v) for k, v in self.test_data.iteritems()
                if self.filter_regex.findall(k)
        ])
        return current_test_list

    def get_test_stats(self):
        return {
            'total': len(self.test_data),
            'filtered': len(self.current_test_list),
            'failed': 1
        }

    def on_filter_change(self, filter_widget, filter_value):
        self.filter_value = filter_value
        if not filter_value:
            self.filter_regex = None
        else:
            regexp_str = '.*?'.join(list(iter(
                filter_value.replace('.', '\.').replace(r'\\', '\\\\')
            )))
            self.filter_regex = re.compile(regexp_str, re.UNICODE + re.IGNORECASE)

        self.init_test_listbox()
        # self.w_main.original_widget._invalidate()
        # self.w_status_line.original_widget._invalidate()
        # self.main_loop.widget._invalidate()
        # self.main_loop.draw_screen()

    def received_output(self, data):
        """
            Parse data received by client and execute encoded action
        """
        logger.debug('received_output %s', data)
        for chunk in data.split('\n'):
            if not chunk:
                continue
            logger.debug('parsing chunk %s', chunk)
            try:
                payload = json.loads(chunk)
                assert 'method' in payload
                assert 'params' in payload
            except Exception as e:
                logger.exception('Failed to parse runner input')

            if payload['method'] == 'item_collected':
                self.runner_item_collected(**payload['params'])


    def runner_item_collected(self, item_id):
        self.test_data[item_id] = {
            'id': item_id
        }
        self.init_test_listbox()

    def run(self):
        self.main_loop = urwid.MainLoop(self.w_main, palette=self.palette,
                       unhandled_input=self.unhandled_keypress)
        self.child_pipe = self.main_loop.watch_pipe(self.received_output)

        self.init_test_data()
        logger.debug('Running main urwid loop')
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

    def run_tests(self, failed_only=True, filtered=None):
        if filtered is None:
            filtered = self.filter_value

        logger.info('Running tests (failed_only: %r, filtered: %r)', failed_only, filtered)
        self._running_tests = True
        self._first_failed_focused = False

        multiprocessing.Process(
            target=self.runner_class.run_tests,
            args=(failed_only, filtered, self.child_pipe)
        ).start()

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

        # TODO use runner

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
        test_data = self.test_data[test_id]
        logger.debug('test_data %s', test_data)
        display_result_state = test_data.get('display_result_state', '')
        if display_result_state in ['failed', 'error'] and not self._first_failed_focused:
            self.w_test_listbox.set_focus(self._get_test_position(test_id))
            self._first_failed_focused = True

        self.test_data[test_id]['widget']._invalidate()
        self.test_data[test_id]['lw_widget']._invalidate()
        # self.w_test_listbox._invalidate()
        self.w_status_line.original_widget._invalidate()

        self.main_loop.draw_screen()

    def show_test_detail(self, widget, test_id):
        test_data = self.test_data[test_id]
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
        result_state_str = self.test_data[test_id].get('result_state', '')
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
        tests = self._get_tests(False, True)
        test_id = tests.keys()[self.w_test_listbox.focus_position]
        next_id = self.get_failed_sibling(test_id, direction)
        if next_id is not None:
            next_pos = self._get_test_position(next_id)
            self.w_test_listbox.set_focus(next_pos, 'above' if direction == 1 else 'below')
            self.w_test_listbox._invalidate()

    def unhandled_keypress(self, key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()
        elif key == '/':
            self.w_main.original_widget.set_focus(2)
        elif key == 'ctrl f':
            self.w_filter_edit.set_edit_text('')
            self.w_main.original_widget.set_focus(2)
        elif key == 'R':
            if not self._running_tests:
                self.run_tests(False)
        elif key == 'r' or key == 'f5':
            if not self._running_tests:
                self.run_tests(True)
        elif key == 'meta down':
            self.focus_failed_sibling(1)

        elif key == 'meta up':
            self.focus_failed_sibling(-1)


def main():
    import sys
    import logging_tools
    path = sys.argv[1] if len(sys.argv) - 1 else '.'
    logging_tools.configure('pytui-ui.log')
    logger.info('Configured logging')

    ui = TestRunnerUI(PytestRunner, path)
    ui.run()

if __name__ == '__main__':
    main()

