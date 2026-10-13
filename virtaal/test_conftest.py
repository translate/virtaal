#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import faulthandler
import gc
import json
import os
import signal
import subprocess
import sys
import textwrap
import warnings
from collections import OrderedDict
from types import SimpleNamespace

import pytest
from _pytest.reports import TestReport

from virtaal import conftest


def _read_lines(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def test_the_cyclic_collector_is_off():
    # Left on, it can free a GTK window from a background thread (#4242).
    assert not gc.isenabled()


def test_child_writes_each_report_for_the_parent(tmp_path, monkeypatch, pytestconfig):
    path = tmp_path / "reports.jsonl"
    monkeypatch.setenv(conftest._REPORTS_ENV, str(path))
    monkeypatch.setattr(conftest, "_config", pytestconfig)
    report = TestReport(
        "a.py::TestA::test_b", ("a.py", 1, "TestA.test_b"), {}, "failed", "boom", "call"
    )

    conftest.pytest_runtest_logreport(report)

    [line] = _read_lines(path)
    replayed = pytestconfig.hook.pytest_report_from_serializable(
        config=pytestconfig, data=line["report"]
    )
    assert (replayed.nodeid, replayed.when, replayed.outcome) == (
        "a.py::TestA::test_b", "call", "failed"
    )


def test_child_writes_each_deprecation_warning_for_the_parent(tmp_path, monkeypatch):
    path = tmp_path / "reports.jsonl"
    monkeypatch.setenv(conftest._REPORTS_ENV, str(path))
    # Keeps this probe warning out of the real end-of-session check.
    monkeypatch.setattr(conftest, "_seen_messages", set())
    message = warnings.WarningMessage(
        DeprecationWarning("probe"), DeprecationWarning, "a.py", 3
    )

    conftest.pytest_warning_recorded(message, "runtest", "a.py::test_b", None)

    assert _read_lines(path) == [{
        "warning": "probe",
        "category": "DeprecationWarning",
        "filename": "a.py",
        "lineno": 3,
        "nodeid": "a.py::test_b",
    }]


def test_a_group_whose_subprocess_never_finishes_fails_each_test(request, monkeypatch):
    item = request.node
    monkeypatch.setattr(
        conftest, "_isolation_group", lambda i: "group" if i is item else None
    )

    monkeypatch.setattr(
        conftest, "_communicate", lambda proc, timeout, stacks_path: ("partial output", True)
    )
    monkeypatch.setattr(conftest.subprocess, "Popen", lambda *args, **kwargs: None)

    conftest._run_group(item, "group")

    reports = conftest._isolated_reports.pop(item.nodeid)
    assert [(r.when, r.outcome) for r in reports] == [
        ("setup", "passed"), ("call", "failed"), ("teardown", "passed")
    ]
    assert "partial output" in str(reports[1].longrepr)



def test_a_group_that_hangs_after_its_tests_pass_warns_with_the_output(
    request, monkeypatch, pytestconfig
):
    # The subprocess wrote every test's reports, then never exited.
    item = request.node
    monkeypatch.setattr(
        conftest, "_isolation_group", lambda i: "group" if i is item else None
    )

    def _communicate(proc, timeout, stacks_path):
        reports_path = stacks_path.replace("stacks.txt", "reports.jsonl")
        with open(reports_path, "w", encoding="utf-8") as f:
            for when in ("setup", "call", "teardown"):
                report = TestReport(item.nodeid, item.location, {}, "passed", None, when)
                data = pytestconfig.hook.pytest_report_to_serializable(
                    config=pytestconfig, report=report
                )
                f.write(json.dumps({"report": data}) + "\n")
        return "Timed out after 120s\nStacks:\nstuck_here", True

    warned = []
    monkeypatch.setattr(conftest, "_communicate", _communicate)
    monkeypatch.setattr(conftest.subprocess, "Popen", lambda *args, **kwargs: None)
    monkeypatch.setattr(conftest, "_warn_hung", lambda i, message: warned.append(message))

    conftest._run_group(item, "group")

    reports = conftest._isolated_reports.pop(item.nodeid)
    assert [r.outcome for r in reports] == ["passed", "passed", "passed"]
    assert len(warned) == 1
    assert "hung after its tests finished" in warned[0]
    assert "stuck_here" in warned[0]

@pytest.mark.skipif(sys.platform == "win32", reason="no SIGUSR1 on Windows")
def test_a_hung_subprocess_is_killed_with_its_stacks(tmp_path):
    stacks_path = tmp_path / "stacks.txt"
    child = textwrap.dedent(f"""
        import faulthandler, signal, time
        stacks = open({str(stacks_path)!r}, "w")
        faulthandler.register(signal.SIGUSR1, file=stacks, all_threads=True)
        print("started", flush=True)

        def stuck_here():
            time.sleep(60)

        stuck_here()
    """)
    proc = subprocess.Popen(
        [sys.executable, "-c", child],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )

    output, timed_out = conftest._communicate(proc, 2, str(stacks_path))

    assert timed_out
    assert proc.returncode is not None
    assert output.startswith("Timed out after 2s")
    assert "started" in output
    assert "stuck_here" in output



@pytest.mark.skipif(sys.platform == "win32", reason="no SIGUSR1 on Windows")
def test_child_dumps_its_stacks_on_sigusr1(tmp_path, monkeypatch, pytestconfig):
    stacks_path = tmp_path / "stacks.txt"
    monkeypatch.setenv(conftest._STACKS_ENV, str(stacks_path))
    monkeypatch.delenv(conftest._STACKS_DIR_ENV, raising=False)
    original = conftest._stacks_file
    monkeypatch.setattr(conftest, "_stacks_file", None)

    conftest.pytest_configure(pytestconfig)
    try:
        os.kill(os.getpid(), signal.SIGUSR1)
    finally:
        conftest._stacks_file.close()
        # Keep this worker's own CI dump (VIRTAAL_STACKS_DIR) working.
        if original is not None:
            faulthandler.register(signal.SIGUSR1, file=original, all_threads=True)
        else:
            faulthandler.unregister(signal.SIGUSR1)

    # Not this test's own frame: faulthandler dumps at most 100 threads,
    # newest first, and a long-lived xdist worker can have more.
    assert "(most recent call first)" in stacks_path.read_text()


def test_warn_hung_records_a_user_warning_with_the_message():
    recorded = []
    item = SimpleNamespace(
        nodeid="a.py::test_b",
        ihook=SimpleNamespace(pytest_warning_recorded=SimpleNamespace(
            call_historic=lambda kwargs: recorded.append(kwargs)
        )),
    )

    conftest._warn_hung(item, "hung here")

    [kwargs] = recorded
    assert kwargs["warning_message"].category is UserWarning
    assert str(kwargs["warning_message"].message) == "hung here"
    assert kwargs["nodeid"] == "a.py::test_b"



def test_main_thread_dump_includes_the_xdist_schedule(tmp_path, monkeypatch):
    monkeypatch.setenv(conftest._STACKS_DIR_ENV, str(tmp_path))
    class Node:
        gateway = SimpleNamespace(id="gw0")
        shutting_down = False

    node = Node()
    sched = SimpleNamespace(
        assigned_work={node: {"a.py": {"a.py::test_done": True, "a.py::test_stuck": False}}},
        workqueue={"b.py": {}},
    )
    monkeypatch.setattr(conftest, "_config", SimpleNamespace(
        pluginmanager=SimpleNamespace(getplugin=lambda name: SimpleNamespace(sched=sched))
    ))

    conftest._dump_main_thread(None, sys._getframe())

    dump = (tmp_path / f"{os.getpid()}-main.txt").read_text()
    assert "test_main_thread_dump_includes_the_xdist_schedule" in dump
    assert "gw0 shutting_down=False pending=['a.py::test_stuck']" in dump
    assert "queued: ['b.py']" in dump


def test_main_thread_dump_without_xdist_has_only_the_stack(tmp_path, monkeypatch):
    monkeypatch.setenv(conftest._STACKS_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(conftest, "_config", SimpleNamespace(
        pluginmanager=SimpleNamespace(getplugin=lambda name: None)
    ))

    conftest._dump_main_thread(None, sys._getframe())

    dump = (tmp_path / f"{os.getpid()}-main.txt").read_text()
    assert "test_main_thread_dump_without_xdist_has_only_the_stack" in dump
    assert "xdist scheduler" not in dump


def test_a_crashed_workers_finished_groups_are_not_queued_again():
    from xdist.scheduler.loadscope import LoadScopeScheduling

    conftest._requeue_only_unfinished_work()
    sched = LoadScopeScheduling.__new__(LoadScopeScheduling)
    class Node:
        shutting_down = True

    node, other = Node(), Node()
    sched.assigned_work = {
        node: {
            "done.py": {"done.py::test_a": True, "done.py::test_b": True},
            "crashed.py": {"crashed.py::test_a": True, "crashed.py::test_b": False},
        },
        other: {},
    }
    sched.workqueue = OrderedDict()

    crashitem = sched.remove_node(node)

    assert crashitem == "crashed.py::test_b"
    assert list(sched.workqueue) == ["crashed.py"]


def test_the_xdist_requeue_fix_is_applied_once():
    from xdist.scheduler.loadscope import LoadScopeScheduling

    conftest._requeue_only_unfinished_work()
    patched = LoadScopeScheduling.remove_node
    conftest._requeue_only_unfinished_work()

    assert LoadScopeScheduling.remove_node is patched


def test_the_xdist_requeue_fix_is_skipped_without_xdist(monkeypatch):
    from xdist.scheduler.loadscope import LoadScopeScheduling

    remove_node = LoadScopeScheduling.remove_node
    monkeypatch.setitem(sys.modules, "xdist", None)

    conftest._requeue_only_unfinished_work()

    assert LoadScopeScheduling.remove_node is remove_node


def test_the_xdist_requeue_fix_is_skipped_once_xdist_has_it(monkeypatch):
    import xdist
    from xdist.scheduler.loadscope import LoadScopeScheduling

    monkeypatch.setattr(LoadScopeScheduling, "remove_node", lambda self, node: None)
    unpatched = LoadScopeScheduling.remove_node
    monkeypatch.setattr(xdist, "__version__", "3.9.0")

    conftest._requeue_only_unfinished_work()

    assert LoadScopeScheduling.remove_node is unpatched
