import sys

def puts(s, newline=True):
    sys.stdout.write(s)
    if newline: sys.stdout.write('\n')
