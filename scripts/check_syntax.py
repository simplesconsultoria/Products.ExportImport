"""Compile every .py file under the given directories with *this* interpreter.

Run under Python 2.4 (``make check``) to catch syntax that newer Pythons
accept but 2.4 does not -- conditional expressions, ``with``, ``except ... as``,
``try``/``except``/``finally`` in one statement. Nothing is written to disk,
so the source can be mounted read-only.
"""

import os
import sys


def check(path):
    """Compile one file; return an error message, or None if it compiles."""
    handle = open(path)
    try:
        source = handle.read()
    finally:
        handle.close()
    try:
        compile(source.replace('\r\n', '\n') + '\n', path, 'exec')
    except SyntaxError:
        error = sys.exc_info()[1]
        return '%s:%s: %s' % (path, error.lineno, error.msg)
    return None


def main(roots):
    """Check every .py file under ``roots``; return the process exit status."""
    checked = 0
    errors = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            for name in filenames:
                if name.endswith('.py'):
                    checked += 1
                    error = check(os.path.join(dirpath, name))
                    if error:
                        errors.append(error)
    for error in errors:
        print(error)
    if not checked:
        print('no Python files found under %s' % ', '.join(roots))
        return 1
    print('checked %d files with Python %s: %d errors' % (
        checked, sys.version.split()[0], len(errors)))
    if errors:
        return 1
    return 0


sys.exit(main(sys.argv[1:]))
