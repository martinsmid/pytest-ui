[![Build Status](https://travis-ci.com/martinsmid/pytest-ui.svg?branch=master)](https://travis-ci.com/martinsmid/pytest-ui)

# pytest-ui
Text User Interface for running python tests. Still in _beta_ version

# pip install
  - provides the cli command `pytui`
  - url on pypi
    https://pypi.python.org/pypi/pytest-ui
  - install using pip
    `pip install pytest-ui`

# controls
  - <kbd>r</kbd>, <kbd>F5</kbd> - run tests (last failed or first run, using filter)
  - <kbd>R</kbd>, <kbd>ctrl</kbd> + <kbd>f5</kbd> - run all tests (using filter)
  - <kbd>/</kbd> - focus filter input
  - <kbd>ctrl</kbd> + <kbd>f</kbd> - clear filter input and focus it
  - <kbd>F4</kbd> - toggle show only failed tests
  - <kbd>alt</kbd> + <kbd>up</kbd>/<kbd>down</kbd> - navigate between failed tests (skipping passed)
  - <kbd>q</kbd> - close window, quit (in main window)

## filter input
By default, filter input is in fuzzy mode. This could be avoided by using dash signs,
where exact match mode is used between a pair of them. For example

abc#match#def will match fuzzy "abc", then exactly "match" and then again fuzzy "def"

# main goals
The goal of this project is to ease the testing process by
  - [x] selecting tests to run using fuzzy filter
  - [x] viewing failed tests stacktrace/output/log while the test suite is still running
  - [x] rerunning failed tests
  - [ ] running a test with debugger
  - [ ] usage as pytest plugin (for custom pytest scripts)
