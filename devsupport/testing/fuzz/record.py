#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Records what goes wrong while a fuzz case runs, as JSON lines.

Events: {"event": "begin", "sweep", "case"}, {"event": "problem", "kind",
"signature", "detail"}, {"event": "note", "text"}, {"event": "end",
"elapsed"}. Every line is flushed, so a case the process died in is the
last "begin" without an "end".
"""

import faulthandler
import json
import logging
import os
import signal
import sys
import time
import traceback

# CI's macOS and Windows runners are about twice as slow as Linux.
SLOW_SECONDS = 10 if sys.platform.startswith('linux') else 20
OUTSIDE_CASE = '(outside a case)'
# faulthandler's dump on a case timeout starts with this; the parent uses
# it to tell a timeout from a crash.
TIMEOUT_MARKER = 'Timeout ('

GLIB_IGNORE = (
    'Theme parsing error',
    # GDK on Windows can't update a layered (tooltip) window without a
    # desktop session, as on CI runners.
    'UpdateLayeredWindow failed',
)
# Not Virtaal problems: translate-toolkit's spelling check logs this once
# per language that has no installed dictionary.
_LOG_IGNORE = (('translate.filters.spelling', 'Dictionary not found'),)
STDERR_MARKER = '@@fuzz '


def _own_frame(path):
    return '/devsupport/testing/fuzz/' in os.path.normpath(path).replace('\\', '/')


def exception_signature(exc_type, tb):
    """Exception type and the innermost Virtaal function it passed through."""
    frames = [f for f in traceback.extract_tb(tb) if not _own_frame(f.filename)]
    for frame in reversed(frames):
        if '/virtaal/' in frame.filename.replace('\\', '/'):
            return '%s %s' % (exc_type.__name__, frame.name)
    return '%s %s' % (exc_type.__name__, frames[-1].name if frames else '')


class Recorder:
    def __init__(self, path, case_timeout, slow_seconds=SLOW_SECONDS):
        self._file = open(path, 'a', encoding='utf-8')
        self.case_timeout = case_timeout
        self.slow_seconds = slow_seconds
        self.sweep = None
        self.case = None
        self._start = None

    def _write(self, **event):
        self._file.write(json.dumps(event, ensure_ascii=True) + '\n')
        self._file.flush()
        if event['event'] in ('begin', 'end', 'done'):
            # GTK writes some criticals straight to stderr; these markers
            # let the parent attribute them to the case.
            sys.stderr.write(STDERR_MARKER + json.dumps(event, ensure_ascii=True) + '\n')
            sys.stderr.flush()

    def begin(self, sweep, case):
        self.end()
        self.sweep, self.case, self._start = sweep, case, time.monotonic()
        self._write(event='begin', sweep=sweep, case=case)
        # A case that hangs ends the process with a stack dump instead of
        # stalling the sweep; the parent records it as a timeout.
        faulthandler.dump_traceback_later(self.case_timeout, exit=True)

    def end(self):
        if self.case is None:
            return
        faulthandler.cancel_dump_traceback_later()
        elapsed = time.monotonic() - self._start
        if self.slow_seconds and elapsed > self.slow_seconds and self.case != OUTSIDE_CASE:
            self.problem('slow', '', 'took %.1f s' % elapsed)
        self._write(event='end', elapsed=round(elapsed, 3))
        self.case = None

    def problem(self, kind, signature, detail=''):
        if self.case is None:
            self.begin(self.sweep or 'setup', OUTSIDE_CASE)
        self._write(event='problem', kind=kind, signature=signature, detail=detail[-4000:])

    def note(self, text):
        self._write(event='note', text=text)

    def done(self):
        """The section finished; without this the parent treats the
        process as having died."""
        self.end()
        self._write(event='done')

    def exception(self, exc_type, exc, tb):
        detail = ''.join(traceback.format_exception(exc_type, exc, tb))
        self.problem('exception', exception_signature(exc_type, tb), detail)

    def install(self):
        """Route uncaught exceptions, logged errors and GLib warnings here.
        PyGObject reports exceptions from signal handlers through
        sys.excepthook, so those are caught too."""
        from gi.repository import GLib

        sys.excepthook = self.exception
        logging.getLogger().addHandler(_LogHandler(self))
        if hasattr(signal, 'SIGTRAP'):
            # G_DEBUG=fatal-criticals stops on a critical with SIGTRAP.
            faulthandler.register(signal.SIGTRAP, chain=True)

        def glib_log(domain, level, message, *data):
            if any(text in message for text in GLIB_IGNORE):
                return
            kind = 'glib-warning' if level & GLib.LogLevelFlags.LEVEL_WARNING else 'critical'
            self.problem(kind, '%s: %s' % (domain or '', message.split('\n')[0][:120]), message)

        flags = (GLib.LogLevelFlags.LEVEL_WARNING | GLib.LogLevelFlags.LEVEL_CRITICAL
                 | GLib.LogLevelFlags.LEVEL_ERROR)
        for domain in ('Gtk', 'Gdk', 'GLib', 'GLib-GObject', 'GLib-GIO', 'Pango', 'GtkSpell', None):
            GLib.log_set_handler(domain, flags, glib_log, None)

    def stub_dialogs(self, main_controller):
        """Modal dialogs would stop the sweep: record them instead."""
        from gi.repository import Gtk

        view = main_controller.view

        def error(title='', message='', markup='', parent=None):
            text = message or markup
            self.problem('error-dialog', text.strip().split('\n')[0][:120], text)

        def unexpected_dialog(dialog, *args, **kwargs):
            self.problem('modal-dialog', type(dialog).__name__, dialog.get_title() or '')
            return Gtk.ResponseType.CANCEL

        view.show_error_dialog = error
        view.show_prompt_dialog = lambda *a, **k: False
        view.show_info_dialog = lambda *a, **k: None
        view.show_save_confirm_dialog = lambda: 'discard'
        view.show_input_dialog = lambda *a, **k: None
        main_controller.get_translator_details = lambda *a, **k: ('Fuzz Tester', 'fuzz@example.org', '')
        Gtk.Dialog.run = unexpected_dialog
        Gtk.NativeDialog.run = unexpected_dialog


class _LogHandler(logging.Handler):
    def __init__(self, recorder):
        super().__init__(level=logging.ERROR)
        self.recorder = recorder

    def emit(self, record):
        message = record.getMessage()
        if any(record.name == name and text in message for name, text in _LOG_IGNORE):
            return
        if record.exc_info and record.exc_info[0]:
            signature = exception_signature(record.exc_info[0], record.exc_info[2])
            message += '\n' + ''.join(traceback.format_exception(*record.exc_info))
        else:
            signature = '%s %s' % (record.name, record.funcName)
        self.recorder.problem('log-error', signature, message)
