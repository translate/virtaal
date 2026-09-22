#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GLib

from virtaal.main import _Deferer


def _deferer(monkeypatch):
    monkeypatch.setattr(_Deferer, '_todo', [])
    return _Deferer()


def test_defer_schedules_idle_add_only_once_for_the_first_job(monkeypatch):
    defer = _deferer(monkeypatch)
    scheduled = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func, priority=None: scheduled.append(func))

    defer(lambda: None)
    defer(lambda: None)

    assert len(scheduled) == 1


def test_defer_runs_queued_jobs_in_order(monkeypatch):
    defer = _deferer(monkeypatch)
    scheduled = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func, priority=None: scheduled.append(func))
    ran = []

    defer(ran.append, 'first')
    defer(ran.append, 'second')
    next_job = scheduled[0]

    still_more = next_job()
    assert ran == ['first']
    assert still_more is True

    still_more = next_job()
    assert ran == ['first', 'second']
    assert still_more is False


def test_next_job_tolerates_being_called_with_an_already_empty_queue(monkeypatch):
    # Documented edge case: a previous next_job() call can be the last
    # one queued in the event loop even though the job it ran added
    # more work - a second, now-redundant next_job() may still fire.
    defer = _deferer(monkeypatch)
    scheduled = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func, priority=None: scheduled.append(func))
    defer(lambda: None)
    next_job = scheduled[0]
    next_job()  # drains the only job

    assert next_job() is False  # must not raise IndexError


def test_a_job_that_defers_more_work_schedules_a_fresh_idle_source(monkeypatch):
    defer = _deferer(monkeypatch)
    scheduled = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func, priority=None: scheduled.append(func))
    ran = []

    def first_job():
        ran.append('first')
        # The queue is empty at this exact point (this job was already
        # popped) - defer() here must schedule a new idle source rather
        # than assume one is still pending.
        defer(ran.append, 'second')

    defer(first_job)
    scheduled[0]()

    assert len(scheduled) == 2
    scheduled[1]()
    assert ran == ['first', 'second']
