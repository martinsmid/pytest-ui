#!/usr/bin/env python
# encoding: utf-8

from __future__ import absolute_import
from __future__ import unicode_literals
from future import standard_library
standard_library.install_aliases()
from builtins import object

import sys
import json
import urwid
import logging
import traceback
import multiprocessing
import _thread
from collections import OrderedDict, defaultdict

from tblib import Traceback

from . import settings
from . import logging_tools
from .logging_tools import get_logger, DEBUG_B
from .common import get_filter_regex, PytestExitcodes
from .runner import PytestRunner


logging_tools.configure('pytui-ui.log')
logger = get_logger('ui')
logger.info('Configured logging')

class TestLine(urwid.Widget):
    _sizing = frozenset(['flow'])
    _selectable = True

    signals = ["click"]

    def __init__(self, test_data, *args, **kwargs):
        self.test_data = test_data
        super(TestLine, self).__init__(*args, **kwargs)

    def rows(self, size, focus=False):
        return 1

    def render(self, size, focus=False):
        result_state_str = self.test_data.get('result_state', '')
        (maxcol,) = size
        attr = []
        title_width = maxcol - 13
        main_attr = (self.test_data.get('runstate'), title_width)
        state_attr = (result_state_str, 10)
        return urwid.TextCanvas(
            [('{} [{:10}]'.format(
                self.test_data['id'][:title_width].ljust(title_width),
                result_state_str[:10]
            )).encode('utf-8')],
            maxcol=maxcol,
            attr=[[main_attr, (None, 2), state_attr, (None, 1)]]
        )

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
            ['Total: {} Filtered: {} Failed: {}'
             .format(stats['total'], stats['filtered'], stats['failed'])
             .encode('utf-8')
            ],
            maxcol=maxcol)


class TestResultWindow(urwid.LineBox):
    _sizing = frozenset(['box'])

    def __init__(self, test_id, text, escape_method):
        self.escape_method = escape_method

        lines = text.split('\n')
        list_items = [
            urwid.AttrMap(urwid.Text(line), None, focus_map='reversed') for line in lines
        ]

        super(TestResultWindow, self).__init__(
            urwid.ListBox(
                urwid.SimpleFocusListWalker(list_items)
            ),
            title=test_id
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


class ErrorPopupWindow(TestResultWindow):
    pass


class Store(object):
    def __init__(self, ui):
        self.test_data = OrderedDict()
        self.ui = ui
        self.filter_regex = None
        self.filter_value = None
        self._show_failed_only = False
        self._show_collected = True

    @property
    def current_test_list(self):
        if not self.filter_regex and not self._show_failed_only and self._show_collected:
            return self.test_data

        return self._get_tests(
            self._show_failed_only,
            bool(self.filter_regex),
            collected=self._show_collected
        )


    def get_test_stats(self):
        return {
            'total': len(self.test_data),
            'filtered': len(self.current_test_list),
            'failed': self.get_failed_test_count()
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

    def get_failed_test_count(self):
        return len([test_id for test_id, test in list(self.current_test_list.items())
                        if self.is_test_failed(test)])

    def _get_tests(self, failed_only=True, filtered=True, include_lf_exempt=True, collected=True):
        logger.info('_get_tests failed_only: %s filtered: %s include_lf_exempt %s collected %s',
                     failed_only, filtered, include_lf_exempt, collected)
        return OrderedDict([
            (test_id, test)
                for test_id, test in list(self.test_data.items())
                if (not failed_only
                  or self.is_test_failed(test))
                and (not filtered
                   or self.is_test_filtered(test_id))
                and (not test.get('last_failed_exempt')
                   or include_lf_exempt)
                and (collected
                   or not test.get('result_state', '') == '')
        ])

    def set_test_result(self, test_id, result_state, output, when, outcome,
                        exc_type=None, exc_value=None, extracted_traceback=None, last_failed_exempt=None):
        """
            Sets test result in internal dictionary. Updates UI.

            Args:
                test_id: An unique string test identifier.
        """
        update_listbox = False

        if not test_id in self.test_data:
            self.test_data[test_id] = {
                'id': test_id
            }
            update_listbox = True

        if extracted_traceback:
            py_traceback = Traceback.from_dict(extracted_traceback).as_traceback()
            extracted_traceback = traceback.extract_tb(py_traceback)
            output += ''.join(
                traceback.format_list(extracted_traceback) +
                [exc_value]
            )

        test_data = self.test_data[test_id]
        test_data['exc_type'] = exc_type
        test_data['exc_value'] = exc_value
        test_data['exc_tb'] = extracted_traceback
        if when == 'call' and last_failed_exempt is not None:
            test_data['last_failed_exempt'] = last_failed_exempt

        # Ignore success, except for the 'call' step
        # ignore successive failure, take only the first
        if (outcome != 'passed' or when == 'call') \
            and not test_data.get('result_state'):
            test_data['result_state'] = result_state
            test_data['output'] = output
            if update_listbox:
                self.ui.init_test_listbox()
            else:
                self.ui.update_test_result(test_data)

        if when == 'teardown':
            test_data['runstate'] = None
            self.ui.update_test_line(test_data)

    def set_test_state(self, test_id, state):
        test_data = self.test_data[test_id]
        test_data['runstate'] = state

        self.ui.update_test_line(test_data)
        self.ui.set_listbox_focus(test_data)

    def set_exception_info(self, test_id, exc_type, exc_value, extracted_traceback, result_state, when):
        self.set_test_result(
            test_id, result_state, exc_value, when, result_state,
            exc_type, exc_value, extracted_traceback
        )

    def set_filter(self, filter_value):
        self.filter_value = filter_value
        self.filter_regex = get_filter_regex(filter_value)

    def invalidate_test_results(self, tests):
        for test_id, test in list(tests.items()):
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

    def is_test_filtered(self, test_id):
        return not self.filter_regex or self.filter_regex.findall(test_id)

    def get_failed_sibling(self, position, direction):
        """
            position is the position in ui listbox, and should be
            equal to position in the list of filtered tests
        """
        tests = self._get_tests(self.show_failed_only, True)
        keys = list(tests.keys())
        next_pos = position

        while True:
            next_pos = next_pos + direction
            if not (next_pos >= 0 and next_pos < len(keys)):
                return None

            if self.is_test_failed(tests[keys[next_pos]]):
                return keys[next_pos]

    def get_next_failed(self, test_id):
        return self.get_failed_sibling(test_id, 1)

    def get_previous_failed(self, test_id):
        return self.get_failed_sibling(test_id, -1)

    @property
    def show_failed_only(self):
        return self._show_failed_only

    @show_failed_only.setter
    def show_failed_only(self, value):
        self._show_failed_only = value
        self.ui.init_test_listbox()

    @property
    def show_collected(self):
        return self._show_collected

    @show_collected.setter
    def show_collected(self, value):
        self._show_collected = value
        self.ui.init_test_listbox()

    def set_pytest_error(self, exitcode, description=None):
        self.show_collected = False
        output = PytestExitcodes.text[exitcode]
        if description is not None:
            output += (
                '\n' +
                '---------- description ----------' +
                '\n' +
                description
            )
        self.ui.show_startup_error(
            'Pytest init/collect failed',
            '{1:s} (pytest exitcode {0:d})'.format(exitcode, output),
        )


class TestRunnerUI(object):
    palette = [
        ('reversed',    '',           'dark green'),
        ('edit',        '',           'black',    '', '',     '#008'),
        ('edit_focus',  '',           'dark gray',   '', '',     '#00b'),
        ('statusline',  'white',      'dark blue',    '', '',     ''),

        # result states
        ('xfail',       'brown',  '',             '', '',     '#b00'),
        ('xpass',       'brown',  '',             '', '',     '#b00'),
        ('failed',      'light red',  '',             '', '',     '#b00'),
        ('error',       'brown',      '',             '', '#f88', '#b00'),
        ('skipped',     'brown', '',             '', '#f88', '#b00'),
        ('ok',          'dark green', '',             '', '',     ''),


        # run states
        ('setup',       'white',      'dark blue',             '', '',     ''),
        ('call',        'white',      'dark blue',             '', '',     ''),
        ('teardown',    'white',      'dark blue',             '', '',     ''),
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

        # process comm
        self.child_pipe = None
        self.pipe_size = multiprocessing.Value('i', 0)
        self.pipe_semaphore = multiprocessing.Event()
        self.receive_buffer = b''
        self.runner_process = None

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
        self.w_test_listbox = self.test_listbox(list(self.store.current_test_list.keys()))
        if self.w_main:
            self.w_status_line.original_widget._invalidate()
            self.w_main.original_widget.widget_list[4] = self.w_test_listbox
            self.w_main.original_widget._invalidate()

    def init_test_data(self):
        if self.runner_process and self.runner_process.is_alive():
            logger.info('Tests are already running')
            return

        self.runner_process = multiprocessing.Process(
            target=self.runner_class.process_init_tests,
            name='pytui-runner',
            args=(self.path, self.child_pipe, self.pipe_size, self.pipe_semaphore)
        )
        self.runner_process.start()

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
        logger.log(DEBUG_B, 'new data on pipe, data size: %s, pipe_size: %s',
                   len(data), self.pipe_size.value)
        self.receive_buffer += data
        for chunk in self.receive_buffer.split(b'\n'):
            if not chunk:
                continue
            try:
                payload = json.loads(chunk.decode('utf-8'))
                assert 'method' in payload
                assert 'params' in payload
            except Exception as e:
                logger.debug('Failed to parse runner input: "%s"', chunk)
                # release the write end if waiting for read
                logger.log(DEBUG_B, 'pipe_size decrease to correct value')
                with self.pipe_size.get_lock():
                    self.pipe_size.value -= len(data)
                    self.pipe_semaphore.set()
                    logger.log(DEBUG_B, 'released semaphore')
                return

            # correct buffer
            self.receive_buffer = self.receive_buffer[len(chunk)+1:]
            logger.debug('handling method %s', payload['method'])
            try:
                if payload['method'] == 'item_collected':
                    self.store.item_collected(**payload['params'])
                elif payload['method'] == 'set_test_result':
                    self.store.set_test_result(**payload['params'])
                elif payload['method'] == 'set_exception_info':
                    self.store.set_exception_info(**payload['params'])
                elif payload['method'] == 'set_test_state':
                    self.store.set_test_state(**payload['params'])
                elif payload['method'] == 'set_pytest_error':
                    self.store.set_pytest_error(**payload['params'])
            except:
                logger.exception('Error in handler "%s"', payload['method'])

        # self.w_main._invalidate()
        # release the write end if waiting for read
        logger.log(DEBUG_B, 'pipe_size decrease to correct value')
        with self.pipe_size.get_lock():
            self.pipe_size.value -= len(data)
            self.pipe_semaphore.set()
            logger.log(DEBUG_B, 'released semaphore')


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
            'center', ('relative', 90), 'middle', ('relative', 85)
        )

    def run_tests(self, failed_only=True, filtered=None):
        if self.runner_process and self.runner_process.is_alive():
            logger.info('Tests are already running')
            return

        self.w_main.original_widget.focus_position = 4

        if filtered is None:
            filtered = self.store.filter_value
        self.store.show_collected = True

        logger.info('Running tests (failed_only: %r, filtered: %r)', failed_only, filtered)
        self._first_failed_focused = False

        tests = self.store._get_tests(failed_only, filtered, include_lf_exempt=False)
        self.store.invalidate_test_results(tests)

        self.runner_process = multiprocessing.Process(
            target=self.runner_class.process_run_tests,
            name='pytui-runner',
            args=(self.path, failed_only, filtered, self.child_pipe, self.pipe_size,
                  self.pipe_semaphore, self.store.filter_value)
        )
        self.runner_process.start()

        # self.w_test_listbox._invalidate()
        # self.w_main._invalidate()
        # self.main_loop.draw_screen()


    def update_test_result(self, test_data):
        display_result_state = test_data.get('result_state', '')
        if display_result_state in ['failed', 'error'] and not self._first_failed_focused:
            try:
                self.w_test_listbox.set_focus(test_data.get('position', 0))
                self._first_failed_focused = True
            except IndexError:
                pass

        if test_data.get('widget'):
            test_data['widget']._invalidate()
            test_data['lw_widget']._invalidate()
            # self.w_test_listbox._invalidate()
            self.w_status_line.original_widget._invalidate()
        else:
            logger.warning('Test "%s" has no ui widget', test_data['id'])

        self.main_loop.draw_screen()

    def update_test_line(self, test_data):
        if test_data.get('widget'):
            test_data['widget']._invalidate()
            test_data['lw_widget']._invalidate()
            self.main_loop.draw_screen()

    def show_test_detail(self, widget, test_id):
        test_data = self.store.test_data[test_id]
        output = test_data.get('output', '')
        # if 'exc_info' in test_data:
        #     output += '\n' + '-'*20 + '\n'
        #     output += '\n'.join(traceback.format_tb(test_data['exc_info'].tb))

        result_window = TestResultWindow(
            test_id,
            output,
            self.popup_close)
        self.popup(result_window)
        result_window.set_focus(0)

    def show_startup_error(self, title, content):
        popup_widget = ErrorPopupWindow(
            title,
            content,
            self.popup_close
        )

        self.popup(popup_widget)
        popup_widget.set_focus(0)

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
        next_id = self.store.get_failed_sibling(self.w_test_listbox.focus_position, direction)
        if next_id is not None:
            next_pos = self.store.get_test_position(next_id)
            self.w_test_listbox.set_focus(next_pos, 'above' if direction == 1 else 'below')
            self.w_test_listbox._invalidate()

    def set_listbox_focus(self, test_data):
        # set listbox focus if not already focused on first failed
        if not self._first_failed_focused:
            try:
                self.w_test_listbox.set_focus(test_data['position'], 'above')
                self.w_test_listbox._invalidate()
            except IndexError:
                pass

    def quit(self):
        self.pipe_semaphore.set()
        if self.runner_process and self.runner_process.is_alive():
            self.runner_process.terminate()
        logger.log(DEBUG_B, 'releasing semaphore')
        raise urwid.ExitMainLoop()

    def unhandled_keypress(self, key):
        if key in ('q', 'Q'):
            self.quit()
        elif key == '/':
            self.w_main.original_widget.set_focus(2)
        elif key == 'ctrl f':
            self.w_filter_edit.set_edit_text('')
            self.w_main.original_widget.set_focus(2)
        elif key == 'R' or key == 'ctrl f5':
            self.run_tests(False)
        elif key == 'r' or key == 'f5':
            self.run_tests(True)
        elif key == 'meta down':
            self.focus_failed_sibling(1)
        elif key == 'meta up':
            self.focus_failed_sibling(-1)
        elif key == 'f4':
            self.store.show_failed_only = not self.store.show_failed_only


def main():
    path = sys.argv[1] if len(sys.argv) - 1 else '.'
    ui = TestRunnerUI(PytestRunner, path)
    ui.run()

if __name__ == '__main__':
    main()

