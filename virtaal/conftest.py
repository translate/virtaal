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
"""

import gettext
from pathlib import Path

import pytest

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
        _seen_messages.add(str(warning_message.message))


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
    langmodel.gettext_lang = lambda name: name


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
