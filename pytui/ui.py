#!/usr/bin/env python
# encoding: utf-8

import json
import urwid
import thread
from common import get_filter_regex
import logging
import traceback
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



class Store(object):
    def __init__(self, ui):
        self.test_data = OrderedDict()
        self.ui = ui
        self.filter_regex = None
        self.filter_value = None

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

    def item_collected(self, item_id):
        if item_id in self.test_data:
            logger.debug('Ignoring collect for %s', item_id)
            return

        self.test_data[item_id] = {
            'id': item_id
        }
        self.ui.init_test_listbox()

    def get_test_position(self, test_id):
        return self.test_data[test_id]['position']

    def _get_tests(self, failed_only=True, filtered=True):
        tests = self.current_test_list if filtered else self.test_data
        return OrderedDict([(test_id, test) for test_id, test in tests.iteritems()
                                  if not failed_only
                                      or (failed_only and self.is_test_failed(test))])

    def set_test_result(self, test_id, result_state, output, when, outcome):
        # Ignore success, except for the test run (call)
        # ignore successive failure, take only the first
        if not test_id in self.test_data:
            self.test_data[test_id] = {
                'id': test_id
            }

        test_data = self.test_data[test_id]
        if (outcome != 'passed' or when == 'call') \
            and not test_data.get('result_state'):
            test_data['result_state'] = result_state
            test_data['output'] = output
            self.ui.update_test_result(test_data)

    def set_exception_info(self, test_id, exc_type, exc_value, extracted_traceback, result, when):
        output = ''.join(
            traceback.format_list(extracted_traceback) +
            [exc_value]
        )
        self.set_test_result(
            test_id,
            result,
            output,
            when,
            'failed'
        )

    def set_filter(self, filter_value):
        self.filter_value = filter_value
        self.filter_regex = get_filter_regex(filter_value)

    def invalidate_test_results(self, tests):
        for test_id, test in tests.iteritems():
            self.clear_test_result(test_id)

    def clear_test_result(self, test_id):
        test_data = self.test_data[test_id]
        test_data.update({
            'result': None,
            'output': '',
            'result_state': ''
        })
        test_data['widget'].test_data['result_state'] = ''
        test_data['widget']._invalidate()

    def is_test_failed(self, test_data):
        failed = not test_data or test_data.get('result_state') in self.ui.runner_class._test_fail_states
        return failed

    def is_test_filtered(self, test):
        if not self.ui:
            return True

        return self.get_test_id(test) in self.ui.current_test_list.keys()

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

    def __init__(self, runner_class, path):
        logger.info('Runner UI init')
        urwid.set_encoding("UTF-8")

        self.runner_class = runner_class
        self.path = path
        self.store = Store(self)

        self.main_loop = None
        self.w_main = None
        self._first_failed_focused = False
        self._running_tests = False

        # process comm
        self.child_pipe = None
        self.pipe_size = multiprocessing.Value('i', 0)
        self.pipe_semaphore = multiprocessing.Event()
        self.receive_buffer = ''

        self.init_main_screen()

    def init_main_screen(self):
        self.w_filter_edit = urwid.Edit('Filter ')
        aw_filter_edit = urwid.AttrMap(self.w_filter_edit, 'edit', 'edit_focus')
        self.w_status_line = urwid.AttrMap(StatusLine(self.store.get_test_stats), 'statusline', '')
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
        self.w_test_listbox = self.test_listbox(self.store.current_test_list.keys())
        if self.w_main:
            self.w_status_line.original_widget._invalidate()
            self.w_main.original_widget.widget_list[4] = self.w_test_listbox
            self.w_main.original_widget._invalidate()

    def init_test_data(self):
        multiprocessing.Process(
            target=self.runner_class.process_init_tests,
            name='pytui-runner',
            args=(self.path, self.child_pipe, self.pipe_size, self.pipe_semaphore)
        ).start()


    def on_filter_change(self, filter_widget, filter_value):
        self.store.set_filter(filter_value)
        self.init_test_listbox()
        # self.w_main.original_widget._invalidate()
        # self.w_status_line.original_widget._invalidate()
        # self.main_loop.widget._invalidate()
        # self.main_loop.draw_screen()

    def received_output(self, data):
        """
            Parse data received by client and execute encoded action
        """
        logger.debug('received output start')
        # release the write end if waiting for read
        with self.pipe_size.get_lock():
            self.pipe_size.value -= len(data)

        # logger.debug('received_output %s', data)
        logger.debug('received_output size: %s, pipe_size: %s',
                     len(data), self.pipe_size.value)
        for chunk in data.split('\n'):
            if not chunk:
                continue
            try:
                if self.receive_buffer:
                    chunk = self.receive_buffer + chunk
                    logger.debug('Using buffer')
                    self.receive_buffer = ''

                payload = json.loads(chunk)
                assert 'method' in payload
                assert 'params' in payload
            except Exception as e:
                logger.exception('Failed to parse runner input: \n"%s"\n', chunk)
                self.receive_buffer += chunk
                return

            try:
                if payload['method'] == 'item_collected':
                    self.store.item_collected(**payload['params'])
                elif payload['method'] == 'set_test_result':
                    self.store.set_test_result(**payload['params'])
                elif payload['method'] == 'set_exception_info':
                    self.store.set_exception_info(**payload['params'])
            except:
                logger.exception('Error in handler "%s"', payload['method'])

        self.pipe_semaphore.set()
        # self.w_main._invalidate()


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

    def run_tests(self, failed_only=True, filtered=None):
        if self._running_tests:
            logger.info('Tests are already running')
            return
        self._running_tests = True

        if filtered is None:
            filtered = self.store.filter_value

        logger.info('Running tests (failed_only: %r, filtered: %r)', failed_only, filtered)
        self._first_failed_focused = False

        tests = self.store._get_tests(failed_only, filtered)
        self.store.invalidate_test_results(tests)

        multiprocessing.Process(
            target=self.runner_class.process_run_tests,
            name='pytui-runner',
            args=(self.path, failed_only, filtered, self.child_pipe, self.pipe_size,
                  self.pipe_semaphore, self.store.filter_value)
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

    def update_test_result(self, test_data):
        display_result_state = test_data.get('result_state', '')
        if display_result_state in ['failed', 'error'] and not self._first_failed_focused:
            self.w_test_listbox.set_focus(test_data.get('position', 0))
            self._first_failed_focused = True

        if test_data.get('widget'):
            test_data['widget']._invalidate()
            test_data['lw_widget']._invalidate()
            # self.w_test_listbox._invalidate()
            self.w_status_line.original_widget._invalidate()
        else:
            logger.warn('Test "%s" has no ui widget', test_data['id'])

        self.main_loop.draw_screen()

    def show_test_detail(self, widget, test_id):
        test_data = self.store.test_data[test_id]
        output = test_data.get('output', '')
        # if 'exc_info' in test_data:
        #     output += '\n' + '-'*20 + '\n'
        #     output += '\n'.join(traceback.format_tb(test_data['exc_info'].tb))

        result_window = TestResultWindow(
            output,
            self.popup_close)
        self.popup(result_window)
        result_window.set_focus(0)

    def popup_close(self):
        self.main_loop.widget = self._popup_original

    def get_list_item(self, test_id, position):
        test_data = self.store.test_data[test_id]
        test_data.update({
            'widget': None,
            'lw_widget': None,
            'position': position,
            'id': test_id,
        })
        test_line = TestLine(test_data)
        test_data['widget'] = test_line
        # logger.debug('widget set for %s: %s', test_id, test_line)
        urwid.connect_signal(test_line, 'click', self.show_test_detail, test_id)
        test_line_attr = urwid.AttrMap(test_line, None, focus_map='reversed')
        test_data['lw_widget'] = test_line_attr
        return test_line_attr

    def test_listbox(self, test_list):
        list_items = []
        for position, test_id in enumerate(test_list):
            test_line_attr = self.get_list_item(test_id, position)
            list_items.append(test_line_attr)
        return urwid.ListBox(urwid.SimpleFocusListWalker(list_items))

    def focus_failed_sibling(self, direction):
        tests = self.store._get_tests(False, True)
        test_id = tests.keys()[self.w_test_listbox.focus_position]
        next_id = self.store.get_failed_sibling(test_id, direction)
        if next_id is not None:
            next_pos = self.store.get_test_position(next_id)
            self.w_test_listbox.set_focus(next_pos, 'above' if direction == 1 else 'below')
            self.w_test_listbox._invalidate()

    def quit(self):
        self.pipe_semaphore.set()
        logger.debug('releasing semaphore')
        raise urwid.ExitMainLoop()

    def unhandled_keypress(self, key):
        if key in ('q', 'Q'):
            self.quit()
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

