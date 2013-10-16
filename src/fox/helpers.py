import os
import pipes
import sys
from subprocess import Popen, STDOUT, PIPE

try:
    import clint.textui
    puts = clint.textui.puts
except ImportError:
    import util
    puts = util.puts


def shellify(args):
    return " ".join(pipes.quote(s) for s in args)


def join_cmds(*cmds):
    return " ; ".join(cmds)


def run_cmd(cmd):
    p = Popen(cmd, stderr=STDOUT, stdout=PIPE, shell=True)
    output = ''
    while True:
        line = p.stdout.readline()
        if not line:
            break
        output += line
        puts(line, newline=False)
    p.wait()
    if p.returncode != 0:
        print "Process exited with non-zero status " + str(p.returncode)
        sys.exit(1)
    return output
