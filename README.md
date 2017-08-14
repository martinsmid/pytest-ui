# pytest-ui
Text User Interface for running python tests.

# controls
  - <kbd>r</kbd>, <kbd>f5</kbd> - run tests (last failed or first run, using filter)
  - <kbd>R</kbd>, <kbd>ctrl</kbd> + <kbd>f5</kbd> - run all tests (using filter)
  - <kbd>/</kbd> - focus filter bar
  - <kbd>ctrl</kbd> + <kbd>f</kbd> - clear filter bar and focus
  - <kbd>f4</kbd> - toggle show only failed tests
  - <kbd>meta</kbd> + <kbd>up</kbd>/<kbd>down</kbd> - navigate between failed tests (skipping passed)
  - <kbd>q<kbd> - quit

# main goals
The goal of this project is to ease the testing process by
  - [x] selecting tests to run using fuzzy filter
  - [x] viewing failed tests stacktrace/output/log while the test suite is still running
  - [x] rerunning failed tests
  - [ ] running a test with debugger
  - [ ] usage as pytest plugin (for custom pytest scripts)
