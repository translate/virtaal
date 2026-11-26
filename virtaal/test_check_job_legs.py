#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import json
import os

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "devsupport", "testing", "check_job_legs.py")


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location("check_job_legs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _job(name, conclusion="success", status="completed"):
    return {"name": name, "status": status, "conclusion": conclusion}


GREEN = [
    _job("test-macos (macos-15)"),
    _job("test-macos (macos-latest)"),
    _job("build-macos-app (macos-15, arm64)"),
    _job("build-macos-app (macos-15-intel, x86_64)"),
    _job("test (3.13)"),
    _job("test-distro"),
    _job("macos", None, "in_progress"),
]


def test_all_legs_succeeded(check):
    assert check.problems(GREEN, ["test-macos", "build-macos-app"]) == []


def test_cancelled_leg_without_runner(check):
    """Merge-queue run 45457581346: one build leg never got a runner."""
    jobs = GREEN[:2] + [_job("build-macos-app (macos-15, arm64)", "cancelled")] + GREEN[3:]
    assert check.problems(jobs, ["test-macos", "build-macos-app"]) == [
        "build-macos-app (macos-15, arm64): cancelled"]


@pytest.mark.parametrize("conclusion", ["failure", "skipped", "timed_out", None])
def test_leg_not_successful(check, conclusion):
    jobs = [_job("test-macos (macos-15)", conclusion, "completed" if conclusion else "queued"),
            _job("test-macos (macos-latest)")]
    assert len(check.problems(jobs, ["test-macos"])) == 1


def test_job_missing(check):
    assert check.problems(GREEN, ["build-flatpak"]) == ["build-flatpak: no jobs in this run"]


def test_name_prefix_is_not_a_leg(check):
    """`test` matches "test (3.13)", not test-distro or test-macos legs."""
    jobs = GREEN + [_job("test-distro (x)", "failure")]
    assert check.problems(jobs, ["test"]) == []
    assert check.problems(jobs, ["test-distro"]) == ["test-distro (x): failure"]


def test_load_paginated_pages_and_lines(check):
    pages = json.dumps({"total_count": 3, "jobs": GREEN[:2]}) + "\n" + json.dumps({"jobs": GREEN[2:3]})
    assert check.load_jobs(pages) == GREEN[:3]
    lines = "\n".join(json.dumps(job) for job in GREEN[:2]) + "\n"
    assert check.load_jobs(lines) == GREEN[:2]


def test_main_exit_status(check, tmp_path, capsys):
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps({"jobs": GREEN}), encoding="utf-8")
    assert check.main(["x", str(path), "test-macos", "build-macos-app"]) == 0
    path.write_text(json.dumps({"jobs": [_job("test-macos (macos-15)", "cancelled")]}), encoding="utf-8")
    assert check.main(["x", str(path), "test-macos"]) == 1
    assert "::error::test-macos (macos-15): cancelled" in capsys.readouterr().out
