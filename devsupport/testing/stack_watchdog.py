#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Run a command; if it outlives a time limit, list its process tree,
dump every thread's stack in each of its pytest processes, then kill it.

    stack_watchdog.py <seconds> -- <command> [args...]

Each pytest process writes its stacks on SIGUSR1 to
$VIRTAAL_STACKS_DIR/<pid>.txt (virtaal/conftest.py). CI's test-macos
uses this for runs that stall instead of failing (#4162).
"""

import glob
import os
import signal
import subprocess
import sys
import time

STACKS_DIR_ENV = "VIRTAAL_STACKS_DIR"
TIMED_OUT = 124


def descendants(pid):
    """Every process below `pid`, parents before their children."""
    ps = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True)
    children = {}
    for line in ps.stdout.splitlines():
        child, parent = (int(field) for field in line.split())
        children.setdefault(parent, []).append(child)
    found = []
    pending = [pid]
    while pending:
        for child in children.get(pending.pop(0), []):
            found.append(child)
            pending.append(child)
    return found


def dump_and_kill(proc, stacks_dir):
    pids = [proc.pid, *descendants(proc.pid)]
    subprocess.run(["ps", "-o", "pid,ppid,stat,etime,command", "-p", ",".join(map(str, pids))])
    for pid in pids:
        try:
            os.kill(pid, signal.SIGUSR1)
        except ProcessLookupError:
            pass
    time.sleep(3)
    for path in sorted(glob.glob(os.path.join(stacks_dir, "*.txt"))):
        with open(path, encoding="utf-8") as f:
            stacks = f.read()
        if stacks:
            print(f"--- {os.path.basename(path)}\n{stacks}", flush=True)
    for pid in reversed(pids):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait()


def main(argv):
    if len(argv) < 4 or argv[2] != "--":
        print(__doc__, file=sys.stderr)
        return 2
    timeout = float(argv[1])
    command = argv[3:]
    proc = subprocess.Popen(command)
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass
    print(f"::error::{command[0]} still running after {timeout:g}s", flush=True)
    dump_and_kill(proc, os.environ.get(STACKS_DIR_ENV, ""))
    return TIMED_OUT


if __name__ == "__main__":
    sys.exit(main(sys.argv))
