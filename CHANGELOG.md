
version 0.3.6b0
---------------

- pytest-compatible interface.


version 0.3.5b0
---------------

- fix bug related to disabled terminal plugin
- add non-fuzzy syntax in filter for exact matching
- increase pytest verbosity for detailed assert diffs.


version 0.3.4b0
---------------

- add --debug/--no-debug option to CLI command
- disable debug logging by default, enable with --debug
- fix log garbage on screen in the debug mode, clear the screen after pytest run


version 0.3.3b0
---------------

- Catch pytest crashes and report them in a popup.


version 0.3.2b0
---------------

- Improve error reporting. Show an popup dialog when collect/testrun errors occur (based on pytest exit code)
- Unfreeze the dependencies in setup.py


version 0.3.1b0
---------------

- Add proper handling for collect-time errors (like module level import errors or syntax errors)


version 0.3b
------------

- Make source python2/3 compatible
- Add exact dependency versions into setup.py
- Workaround the problem with cyclic logging of stdout/printing stdout logs to stdout caused by pytest/capture or pytest/logging
