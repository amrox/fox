import os
import sys


def puts(s, newline=True):
    sys.stdout.write(s)
    if newline:
        sys.stdout.write('\n')


def makedirs(path):
    """Convenience method that ignores errors if directory already exists."""
    try:
        os.makedirs(path)
    except OSError, e:
        if e.errno == 17:
            pass  # directory already exists
        else:
            raise e
