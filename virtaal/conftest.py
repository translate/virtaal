"""Fail the test suite on any *new* DeprecationWarning, without ever
raising one mid-test.

A pytest `filterwarnings = ["error::DeprecationWarning"]` rule was
tried and rejected: several deprecated GTK calls fire their warning
from inside a live GTK/PyGObject C call, and turning that into a
raised Python exception mid-call measurably worsens this suite's
pre-existing native segfault flakiness (35% vs 5% crash rate over 40
trials). Instead, warnings are only ever recorded as they happen
(`"always"`, never `"error"`) and checked once at the very end, so a
run that would otherwise pass is never interrupted mid-test.

Known, not-yet-fixed warnings are listed in
devsupport/known-deprecation-warnings.txt (one message prefix per
line, `#`-comments allowed) - remove a line there once its warning is
actually fixed. Anything NOT matching that list fails the run.
"""

import warnings
from pathlib import Path

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


def _record_warning(message, category, filename, lineno, file=None, line=None):
    if issubclass(category, _WATCHED_CATEGORIES):
        _seen_messages.add(str(message))


def pytest_configure(config):
    warnings.filterwarnings("always", category=DeprecationWarning)
    warnings.filterwarnings("always", category=PendingDeprecationWarning)
    warnings.showwarning = _record_warning


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
