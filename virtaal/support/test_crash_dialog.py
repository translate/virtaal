#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import sys
from urllib.parse import parse_qs, urlsplit

import pytest

from virtaal.support import crash_dialog


@pytest.fixture(autouse=True)
def _fresh_shown_errors(monkeypatch):
    monkeypatch.setattr(crash_dialog, '_shown_errors', set())


def _exc_info(exc_type, message):
    try:
        raise exc_type(message)
    except exc_type:
        return sys.exc_info()


def test_install_sets_excepthook(monkeypatch):
    monkeypatch.setattr(sys, 'excepthook', sys.__excepthook__)
    crash_dialog.install()
    assert sys.excepthook is crash_dialog._on_uncaught_exception


def test_truncate_for_report_leaves_short_text_alone():
    text = "short traceback"
    assert crash_dialog.truncate_for_report(text, limit=100) == text


def test_truncate_for_report_keeps_the_tail_of_long_text():
    text = "x" * 50 + "THE ACTUAL ERROR"
    truncated = crash_dialog.truncate_for_report(text, limit=20)
    assert truncated.endswith("THE ACTUAL ERROR")
    assert len(truncated) < len(text)


def test_keyboard_interrupt_bypasses_the_dialog(monkeypatch):
    calls = []
    monkeypatch.setattr(crash_dialog, '_show_dialog', lambda text: calls.append(text))
    monkeypatch.setattr(sys, '__excepthook__', lambda *a: calls.append('default-hook'))

    crash_dialog._on_uncaught_exception(*_exc_info(KeyboardInterrupt, ''))

    assert calls == ['default-hook']


def test_uncaught_exception_shows_dialog_and_logs(monkeypatch, caplog):
    calls = []
    monkeypatch.setattr(crash_dialog, '_show_dialog', lambda text: calls.append(text))

    crash_dialog._on_uncaught_exception(*_exc_info(ValueError, 'boom'))

    assert len(calls) == 1
    assert 'ValueError: boom' in calls[0]
    assert 'Uncaught exception' in caplog.text


def test_repeated_error_shows_dialog_once_and_logs_repeats(monkeypatch, caplog):
    calls = []
    monkeypatch.setattr(crash_dialog, '_show_dialog', lambda text: calls.append(text))

    # Same raise site, different message - still the same error.
    for message in ('index 1', 'index 2', 'index 3'):
        crash_dialog._on_uncaught_exception(*_exc_info(IndexError, message))

    assert len(calls) == 1
    assert caplog.text.count('Uncaught exception repeated: IndexError') == 2


def test_different_error_still_shows_its_own_dialog(monkeypatch):
    calls = []
    monkeypatch.setattr(crash_dialog, '_show_dialog', lambda text: calls.append(text))

    crash_dialog._on_uncaught_exception(*_exc_info(ValueError, 'boom'))
    crash_dialog._on_uncaught_exception(*_exc_info(KeyError, 'boom'))

    assert len(calls) == 2


def test_build_report_url_labels_it_as_a_traceback():
    url = crash_dialog.build_report_url("Traceback...\nValueError: boom")
    fields = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}

    assert fields['labels'] == 'bug,traceback'
    assert 'ValueError: boom' in fields['logs']


def test_dialog_raising_does_not_recurse_or_propagate(monkeypatch):
    calls = []

    def boom(text):
        calls.append(text)
        raise RuntimeError('dialog construction failed')

    monkeypatch.setattr(crash_dialog, '_show_dialog', boom)

    crash_dialog._on_uncaught_exception(*_exc_info(ValueError, 'boom'))  # must not raise

    assert len(calls) == 1


# _show_dialog(): dialog focus on macOS (#3865-adjacent - same missing
# show()/present() bug, found while auditing for other hidden instances)

def test_show_dialog_shows_before_presenting(monkeypatch):
    from gi.repository import Gtk

    calls = []

    class _FakeDialog:
        def __init__(self, *args, **kwargs):
            pass

        def format_secondary_text(self, text):
            pass

        def get_content_area(self):
            return Gtk.Box()

        def add_button(self, label, response):
            pass

        def set_default_response(self, response):
            pass

        def show(self):
            calls.append('show')

        def present(self):
            calls.append('present')

        def run(self):
            calls.append('run')
            return Gtk.ResponseType.CLOSE

        def destroy(self):
            calls.append('destroy')

    monkeypatch.setattr(Gtk, 'MessageDialog', _FakeDialog)

    crash_dialog._show_dialog('traceback text')

    assert calls == ['show', 'present', 'run', 'destroy']
