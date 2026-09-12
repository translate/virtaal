#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Shows a dialog with the traceback on any uncaught exception, with a
button to open a pre-filled bug report (see FEATURE-CRASH-REPORTING.md).
Covers exceptions from GTK/GLib callbacks too - PyGObject already
routes those through sys.excepthook rather than crashing outright."""

import logging
import sys
import traceback

# Comfortably under GitHub's URL length limit even after the other
# prefilled fields and percent-encoding overhead; the full traceback is
# always in the log file regardless.
MAX_REPORTED_TRACEBACK_CHARS = 4000

_showing_dialog = False


def install():
    sys.excepthook = _on_uncaught_exception


def _on_uncaught_exception(exc_type, exc_value, tb):
    global _showing_dialog

    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(exc_type, exc_value, tb)
        return

    full_text = "".join(traceback.format_exception(exc_type, exc_value, tb))
    logging.error("Uncaught exception:\n%s", full_text)

    if _showing_dialog:
        # The dialog itself raised - don't recurse into it again.
        return

    try:
        _showing_dialog = True
        _show_dialog(full_text)
    except Exception:
        logging.exception("Failed to show the crash dialog")
    finally:
        _showing_dialog = False


def truncate_for_report(text, limit=MAX_REPORTED_TRACEBACK_CHARS):
    """Keep the tail of a traceback - that's where the actual exception
        is - noting that it was cut if so."""
    if len(text) <= limit:
        return text
    return "(truncated - see the full log)\n...\n" + text[-limit:]


def build_report_url(full_text):
    from virtaal.support.bug_report import build_bug_report_url
    return build_bug_report_url(extra_fields={
        'logs': truncate_for_report(full_text),
        # Every report from here has a real traceback, unlike the
        # generic Help > Report a Bug path - label it as such.
        'labels': 'bug,traceback',
    })


def _show_dialog(full_text):
    from gi.repository import Gtk

    from virtaal.support import openmailto

    dialog = Gtk.MessageDialog(
        None, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR, Gtk.ButtonsType.NONE,
        _("Virtaal hit an unexpected error"))
    dialog.format_secondary_text(
        _("This might not affect your current work, but if it keeps happening, "
          "reporting it helps get it fixed."))

    expander = Gtk.Expander(label=_("Details"))
    textview = Gtk.TextView(editable=False, monospace=True)
    textview.get_buffer().set_text(full_text)
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_size_request(480, 200)
    scrolled.add(textview)
    expander.add(scrolled)
    dialog.get_content_area().pack_start(expander, True, True, 0)
    expander.show_all()

    dialog.add_button(_("Close"), Gtk.ResponseType.CLOSE)
    dialog.add_button(_("Report This Bug…"), Gtk.ResponseType.ACCEPT)
    dialog.set_default_response(Gtk.ResponseType.ACCEPT)

    response = dialog.run()
    dialog.destroy()
    if response == Gtk.ResponseType.ACCEPT:
        openmailto.open(build_report_url(full_text))
