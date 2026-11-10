#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Regular expressions that can take exponential time, run in a child
process with a time limit (#4692).

Python's re backtracks without limit: nested repetition such as
"(a+)+$" can run for minutes on one short string, holding the GIL, so
neither a thread nor a deadline checked between strings can stop it.
Only expressions that repeat a repetition or an alternation are sent to
the child; the rest run in-process as before.
"""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time

TIME_LIMIT = 2
"""Seconds a risky search may take once the child is ready to match."""
STARTUP_LIMIT = 15
"""Seconds the child may take to start (a frozen build may unpack first)."""
_POLL = 0.01

try:
    from re import _parser as _sre_parse
except ImportError:  # Python < 3.11
    import sre_parse as _sre_parse

# A possessive repeat (Python 3.11+) never backtracks into itself.
_REPEATS = ('MAX_REPEAT', 'MIN_REPEAT')


class SearchTimeout(Exception):
    """The search took longer than TIME_LIMIT, or its child process
        failed, and was stopped."""


def is_risky(pattern, flags=0):
    """Whether pattern repeats a repetition or an alternation, the shapes
        that make re backtrack exponentially."""
    try:
        parsed = _sre_parse.parse(pattern, flags)
    except Exception:
        return False  # re.compile() reports it
    return _nested(parsed, False)


def _nested(subpattern, in_repeat):
    for op, av in subpattern:
        name = str(op)
        if name in _REPEATS:
            _min, max_, item = av
            repeats = max_ > 1
            if repeats and in_repeat:
                return True
            if _nested(item, in_repeat or repeats):
                return True
        elif name == 'BRANCH':
            if in_repeat:
                return True
            if any(_nested(branch, in_repeat) for branch in av[1]):
                return True
        elif name == 'SUBPATTERN':
            if _nested(av[-1], in_repeat):
                return True
        elif name in ('ASSERT', 'ASSERT_NOT'):
            if _nested(av[1], in_repeat):
                return True
        elif name == 'ATOMIC_GROUP':
            if _nested(av, in_repeat):
                return True
        elif name == 'GROUPREF_EXISTS':
            if any(_nested(part, in_repeat) for part in av[1:] if part):
                return True
    return False


def find_spans(pattern, flags, strings, timeout=None):
    """The (start, end) of every match of pattern in each of strings,
        found in a child process. Raises SearchTimeout if matching takes
        longer than timeout (default TIME_LIMIT) seconds, or the child
        takes longer than STARTUP_LIMIT to start or fails."""
    from virtaal.support import helperprocess

    if timeout is None:
        timeout = TIME_LIMIT

    with tempfile.TemporaryDirectory(prefix='virtaal-search-') as tmp:
        request = os.path.join(tmp, 'request.json')
        result = os.path.join(tmp, 'result.json')
        ready = os.path.join(tmp, 'ready')
        with open(request, 'w', encoding='utf-8') as f:
            json.dump({'pattern': pattern, 'flags': int(flags), 'strings': strings}, f)
        try:
            proc = subprocess.Popen(
                helperprocess.command(__name__) + [request, result, ready],
                env=helperprocess.env(),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            logging.warning('Search for %r stopped: %s', pattern, e)
            raise SearchTimeout(pattern) from None
        try:
            stage = _wait(proc, ready, timeout)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
        if stage == 'startup':
            logging.warning('Search for %r stopped: the search process took over %s seconds to start',
                            pattern, STARTUP_LIMIT)
            raise SearchTimeout(pattern)
        if stage == 'search':
            logging.warning('Search for %r stopped after %s seconds', pattern, timeout)
            raise SearchTimeout(pattern)
        if proc.returncode:
            logging.warning('Search for %r stopped: exit status %s', pattern, proc.returncode)
            raise SearchTimeout(pattern)
        with open(result, encoding='utf-8') as f:
            return [[tuple(span) for span in spans] for spans in json.load(f)]


def _wait(proc, ready, timeout):
    """Wait for proc to finish: up to STARTUP_LIMIT seconds for it to
        create ready, then timeout seconds more. The stage it ran out of
        time in, or None once it has exited."""
    deadline = time.monotonic() + STARTUP_LIMIT
    while not os.path.exists(ready):
        if proc.poll() is not None:
            return None
        if time.monotonic() > deadline:
            return 'startup'
        time.sleep(_POLL)
    try:
        proc.wait(timeout)
    except subprocess.TimeoutExpired:
        return 'search'
    return None


def _main(request, result, ready):
    with open(request, encoding='utf-8') as f:
        request = json.load(f)
    regexp = re.compile(request['pattern'], request['flags'])
    # Started: the time limit counts from here.
    open(ready, 'w').close()
    spans = [[m.span() for m in regexp.finditer(string)] for string in request['strings']]
    with open(result, 'w', encoding='utf-8') as f:
        json.dump(spans, f)


if __name__ == '__main__':
    _main(*sys.argv[1:4])
