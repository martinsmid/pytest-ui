# pytest-ui
Text User Interface for running python tests. Still in _beta_ version

# pip install
  - provides the cli command `pytui`
  - url on pypi
    https://pypi.python.org/pypi/pytest-ui
  - install using pip
    `pip install pytest-ui`

# controls
  - <kbd>r</kbd>, <kbd>f5</kbd> - run tests (last failed or first run, using filter)
  - <kbd>R</kbd>, <kbd>ctrl</kbd> + <kbd>f5</kbd> - run all tests (using filter)
  - <kbd>/</kbd> - focus filter input
  - <kbd>ctrl</kbd> + <kbd>f</kbd> - clear filter input and focus it
  - <kbd>f4</kbd> - toggle show only failed tests
  - <kbd>alt</kbd> + <kbd>up</kbd>/<kbd>down</kbd> - navigate between failed tests (skipping passed)
  - <kbd>q</kbd> - close window, quit (in main window)

# main goals
The goal of this project is to ease the testing process by
  - [x] selecting tests to run using fuzzy filter
  - [x] viewing failed tests stacktrace/output/log while the test suite is still running
  - [x] rerunning failed tests
  - [ ] running a test with debugger
  - [ ] usage as pytest plugin (for custom pytest scripts)
