"""Fail the test suite on any *new* DeprecationWarning, without ever
raising one mid-test.

A pytest `filterwarnings = ["error::DeprecationWarning"]` rule was
tried and rejected: several deprecated GTK calls fire their warning
from inside a live GTK/PyGObject C call, and turning that into a
raised Python exception mid-call measurably worsens this suite's
pre-existing native segfault flakiness (35% vs 5% crash rate over 40
trials). Instead, warnings are only ever recorded as they happen and
checked once at the very end, so a run that would otherwise pass is
never interrupted mid-test.

Warnings are collected via the `pytest_warning_recorded` hook, not by
assigning `warnings.showwarning` directly - pytest's own warnings
plugin wraps every test phase in `warnings.catch_warnings(record=True)`,
which replaces `showwarning` for the phase's whole duration and so
silently shadows a plain module-level override for as long as any test
is actually running (verified directly: a `showwarning`-based version
of this hook recorded nothing and always exited 0, even for a warning
pytest's own summary showed it had captured).

Known, not-yet-fixed warnings are listed in
devsupport/known-deprecation-warnings.txt (one message prefix per
line, `#`-comments allowed) - remove a line there once its warning is
actually fixed. Anything NOT matching that list fails the run.

A few specific, known-harmless warnings are filtered out entirely via
pyproject.toml's own `filterwarnings` instead of being listed here -
not the same thing as the blanket `error::DeprecationWarning` rule
rejected above. Those never reach this hook at all any more (a
pytest-xdist worker-crash risk, not this file's own concern), so don't
expect them to show up in _seen_messages.
"""

import builtins
import gettext
import json
import os
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import pytest
from _pytest import runner

from virtaal.models import langmodel
from virtaal.support import statsdb

_ALLOWLIST_PATH = (
    Path(__file__).resolve().parent.parent
    / "devsupport"
    / "known-deprecation-warnings.txt"
)

_WATCHED_CATEGORIES = (DeprecationWarning, PendingDeprecationWarning)

_seen_messages = set()


def _load_allowlist():
    prefixes = []
    with open(_ALLOWLIST_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                prefixes.append(line)
    return prefixes


def pytest_warning_recorded(warning_message, when, nodeid, location):
    if issubclass(warning_message.category, _WATCHED_CATEGORIES):
        message = str(warning_message.message)
        _seen_messages.add(message)
        path = os.environ.get(_REPORTS_ENV)
        if path:
            # An isolated subprocess hands its warnings back to the
            # parent, which re-records them (see _run_group).
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "warning": message,
                    "category": warning_message.category.__name__,
                    "filename": warning_message.filename,
                    "lineno": warning_message.lineno,
                    "nodeid": nodeid,
                }) + "\n")


def _is_testscaffolding_subclass(cls):
    # virtaal/test has no __init__.py, so test files import this bare
    # (`from test_scaffolding import TestScaffolding`, pytest's legacy
    # rootdir-relative import mode) while this conftest imports it
    # fully-qualified - two distinct module objects for the same file,
    # so a plain issubclass() against either import silently never
    # matches the other. Compare by name instead.
    return any(
        c.__module__.rsplit(".", 1)[-1] == "test_scaffolding" and c.__name__ == "TestScaffolding"
        for c in cls.__mro__
    )


# Leaked real toplevels crash an xdist worker natively on macOS (no
# Python traceback); a fresh process per file avoids it.
_ISOLATED_FILES = {"test_popupwidgetbutton.py"}

_CHILD_ENV = "_VIRTAAL_TESTSCAFFOLDING_ISOLATED"
_REPORTS_ENV = "_VIRTAAL_ISOLATED_REPORTS"

_config = None
_isolated_reports = {}


def _isolation_group(item):
    """The tests that share one fresh subprocess on macOS: a whole
    TestScaffolding class (setup_class builds its one MainController),
    or a whole _ISOLATED_FILES file. None if the test runs in-process."""
    path = item.nodeid.split("::", 1)[0]
    cls = getattr(item, "cls", None)
    if cls is not None and _is_testscaffolding_subclass(cls):
        return f"{path}::{cls.__name__}"
    if item.path.name in _ISOLATED_FILES:
        return path
    return None


def _child_nodeid(item, group):
    # Under `--dist loadgroup` xdist appends "@<group>" to the nodeid.
    return item.nodeid.removesuffix("@" + group)


def _isolating():
    return sys.platform == "darwin" and not os.environ.get(_CHILD_ENV)


def pytest_configure(config):
    global _config
    _config = config


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(session, config, items):
    if not _isolating():
        return
    for item in items:
        group = _isolation_group(item)
        if group is not None:
            # Keeps a group on one worker under `--dist loadgroup`;
            # the subprocess enforces the per-test timeout itself.
            item.add_marker(pytest.mark.xdist_group(group))
            item.add_marker(pytest.mark.timeout(0))


def pytest_runtest_logreport(report):
    path = os.environ.get(_REPORTS_ENV)
    if path:
        data = _config.hook.pytest_report_to_serializable(config=_config, report=report)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"report": data}) + "\n")


def _make_report(item, when, passed, output=""):
    if passed:
        call = runner.CallInfo.from_call(lambda: None, when)
    else:
        def _raise():
            raise AssertionError(
                "macOS subprocess-isolated run failed (issue #3738):\n" + output
            )
        call = runner.CallInfo.from_call(_raise, when)
    return runner.pytest_runtest_makereport(item, call)


def _run_group(item, group):
    """Run every collected test in `group` in one fresh pytest
    subprocess, storing each test's own reports in _isolated_reports."""
    members = [i for i in item.session.items if _isolation_group(i) == group]
    nodeids = [_child_nodeid(i, group) for i in members]
    # A per-invocation --basetemp, not pytest's shared default
    # (/tmp/pytest-of-<user>/): concurrent xdist workers each spawning
    # their own subprocess otherwise race on that shared root's
    # pytest-current symlink retention/cleanup.
    with tempfile.TemporaryDirectory(prefix="virtaal-testscaffolding-isolated-") as tmp:
        reports_path = os.path.join(tmp, "reports.jsonl")
        try:
            proc = subprocess.run(
                [
                    sys.executable, "-m", "pytest",
                    "-p", "no:cacheprovider",
                    "--basetemp", os.path.join(tmp, "basetemp"),
                    "-q", *nodeids,
                ],
                capture_output=True,
                text=True,
                timeout=60 + 30 * len(nodeids),
                cwd=str(Path(__file__).resolve().parent.parent),
                env={**os.environ, _CHILD_ENV: "1", _REPORTS_ENV: reports_path},
            )
            output = proc.stdout + proc.stderr
        except subprocess.TimeoutExpired as e:
            output = f"{e}\n{e.stdout or ''}{e.stderr or ''}"
        lines = []
        if os.path.exists(reports_path):
            with open(reports_path, encoding="utf-8") as f:
                lines = [json.loads(line) for line in f]

    by_nodeid = {}
    for line in lines:
        if "warning" in line:
            category = getattr(builtins, line["category"])
            item.ihook.pytest_warning_recorded.call_historic(kwargs={
                "warning_message": warnings.WarningMessage(
                    category(line["warning"]), category, line["filename"], line["lineno"]
                ),
                "when": "runtest",
                "nodeid": line["nodeid"],
                "location": None,
            })
            continue
        report = item.config.hook.pytest_report_from_serializable(
            config=item.config, data=line["report"]
        )
        if isinstance(report.longrepr, list):
            # A skip's (path, lineno, reason); JSON turned it into a list.
            report.longrepr = tuple(report.longrepr)
        by_nodeid.setdefault(report.nodeid, []).append(report)
    for member in members:
        reports = by_nodeid.get(_child_nodeid(member, group), [])
        for report in reports:
            report.nodeid = member.nodeid
        if not any(r.when == "teardown" for r in reports):
            # The subprocess died or hung before this test finished.
            reports = [
                _make_report(member, when, when != "call", output)
                for when in ("setup", "call", "teardown")
            ]
        _isolated_reports[member.nodeid] = reports


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    """TestScaffolding builds a real MainController(), which on macOS
    engages GtkosxApplication - a documented wrapper around Cocoa's
    NSApplication, itself a process-wide singleton (issue #3738).
    Running two of these in the same process hangs (second
    construction fights the singleton); running them via
    pytest-xdist's normal in-process model or via fork-based isolation
    (pytest-forked) both hit real, unfixable native crashes/hangs.
    A genuinely fresh subprocess (re-exec, not fork) has no such
    inherited state, so on macOS each TestScaffolding class - one
    MainController, as setup_class builds it - runs as its own
    `pytest` child process, as does each _ISOLATED_FILES file. The
    first test of a group runs the whole group; the rest replay its
    stored reports. Other platforms are unaffected."""
    if not _isolating():
        return None
    group = _isolation_group(item)
    if group is None:
        return None

    ihook = item.ihook
    ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
    if item.nodeid not in _isolated_reports:
        _run_group(item, group)
    for report in _isolated_reports.pop(item.nodeid):
        ihook.pytest_runtest_logreport(report=report)
    item.session._setupstate.teardown_exact(nextitem)
    ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)
    return True


@pytest.fixture(autouse=True, scope="session")
def _force_english_translations():
    """pan_app installs a real gettext translation at import time,
    keyed off a developer's own real uilang setting in their local
    virtaal.ini - tests asserting a literal English string would
    otherwise pass or fail depending on whose machine runs them.
    NullTranslations().install() makes _()/ngettext() pass strings
    through unchanged, independent of that.

    langmodel.gettext_lang is a separate translator bound from the
    same real uilang, via the system's iso_639 catalog, that renders
    LanguageModel(...).name - untouched by the patch above since it
    bypasses the builtin _() entirely."""
    gettext.NullTranslations().install()
    langmodel.gettext_lang = lambda name, code=None: name


@pytest.fixture(autouse=True, scope="session")
def _isolate_stats_cache(tmp_path_factory):
    """Building a StoreModel (several test files) opens
    statsdb.StatsCache's default ~/.translate_toolkit/stats.db - under
    pytest-xdist, concurrent workers hitting that one real, shared file
    race on its delete-and-recreate logic (clear_old_data). Give each
    worker its own file instead."""
    statsdb.StatsCache.defaultfile = str(tmp_path_factory.mktemp("stats") / "stats.db")


def pytest_sessionfinish(session, exitstatus):
    allowed_prefixes = _load_allowlist()
    unexpected = [
        message
        for message in _seen_messages
        if not any(message.startswith(prefix) for prefix in allowed_prefixes)
    ]
    if unexpected:
        print("\nUnexpected DeprecationWarning(s) not in the allowlist:")
        for message in sorted(unexpected):
            print(f"  {message}")
        print(f"\nAllowlist: {_ALLOWLIST_PATH}")
        session.exitstatus = 1
