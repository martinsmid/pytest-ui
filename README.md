# pytest-ui
Text User Interface for running python tests.

# controls
  - r, f5 - run tests (last failed or first run, using filter)
  - R, ctrl + f5 - run all tests (using filter)
  - / - focus filter bar
  - ctrl + f - clear filter bar and focus
  - f4 - toggle show only failed tests
  - meta + up/down - navigate between failed tests (skipping passed)
  - q - quit

# main goals
The goal of this project is to ease the testing process by
  - [x] selecting tests to run using fuzzy filter
  - [x] viewing failed tests stacktrace/output/log while the test suite is still running
  - [x] rerunning failed tests
  - [ ] running a test with debugger
  - [ ] usage as pytest plugin (for custom pytest scripts)
