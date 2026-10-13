#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Unit state lists from a store in memory, and filling the stats cache
in a child process so that opening or saving a file doesn't wait for it.

A child process, not a thread: the fill holds the GIL long enough to
make opening a large file twice as slow."""

import logging
import subprocess
import sys

from virtaal.support import statsdb

_running = None
# One fill at a time: SQLite allows a single writer.
_queued = []


def state_lists(store):
    """Return what C{StatsCache().filestatestats(..., extended=True)}
        returns, from the units in C{store}."""
    stats = statsdb.emptyfilestats()
    stats['extended'] = {}
    for index, unit in enumerate(store.units):
        if not unit.istranslatable():
            continue
        stats[statsdb.state_strings[statsdb.statefordb(unit)]].append(index)
        stats['extended'].setdefault(unit.get_state_id(), []).append(index)
        stats['total'].append(index)
    return stats


def fill_in_background(filename):
    """Cache the stats of the file on disk at C{filename}."""
    _queued.append(filename)
    if _running is None:
        _start_next()


def wait():
    """Block until every queued fill is done. Call before using
        L{statsdb.StatsCache}, which a running fill may have locked."""
    while _running is not None:
        _running.wait()
        _finish(_running)


def _start_next():
    global _running
    _running = None
    if not _queued:
        return
    from gi.repository import GLib

    from virtaal.support import helperprocess

    filename = _queued.pop(0)
    statsdb.StatsCache()  # Sets the default stats file.
    _running = subprocess.Popen(
        helperprocess.command(__name__) + [statsdb.StatsCache.defaultfile, filename],
        env=helperprocess.env())
    _running.filename = filename
    GLib.timeout_add(200, _poll, _running)


def _poll(proc):
    if proc is not _running:
        return False
    if proc.poll() is None:
        return True
    _finish(proc)
    return False


def _finish(proc):
    if proc.returncode:
        logging.debug('Could not cache the stats of %s (exit status %s)', proc.filename, proc.returncode)
    _start_next()


if __name__ == '__main__':
    statsfile, filename = sys.argv[1:]
    try:
        statsdb.StatsCache(statsfile).filestatestats(filename)
    except Exception:
        sys.exit(1)
