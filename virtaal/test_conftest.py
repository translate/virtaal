#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import faulthandler
import json
import os
import signal
import subprocess
import sys
import textwrap
import warnings
from types import SimpleNamespace

import pytest
from _pytest.reports import TestReport

from virtaal import conftest


def _read_lines(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


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
    monkeypatch.setattr(conftest, "_stacks_file", None)

    conftest.pytest_configure(pytestconfig)
    try:
        os.kill(os.getpid(), signal.SIGUSR1)
    finally:
        faulthandler.unregister(signal.SIGUSR1)
        conftest._stacks_file.close()

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
