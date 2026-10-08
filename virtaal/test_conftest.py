#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import json
import subprocess
import warnings

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

    def _hang(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs["timeout"], output="partial output")

    monkeypatch.setattr(conftest.subprocess, "run", _hang)

    conftest._run_group(item, "group")

    reports = conftest._isolated_reports.pop(item.nodeid)
    assert [(r.when, r.outcome) for r in reports] == [
        ("setup", "passed"), ("call", "failed"), ("teardown", "passed")
    ]
    assert "partial output" in str(reports[1].longrepr)
