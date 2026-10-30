#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

__all__ = ['entry_value', 'forall_widgets', 'keep_one_line', 'one_line']

import functools
import re

from gi.repository import GLib, Gtk

# Line breaks (CR, LF, CRLF, Unicode separators) and tabs.
_BREAKS = re.compile('[\t\n\v\f\r\x1c-\x1e\x85\u2028\u2029]+')


@functools.singledispatch
def get_children(widget):
    return []


@get_children.register(Gtk.Container)
def get_children_container(widget):
    return widget.get_children()

def forall_widgets(f, widget):
    f(widget)
    for child in get_children(widget):
        forall_widgets(f, child)


def one_line(text):
    """C{text} with each run of line breaks and tabs as one space."""
    return _BREAKS.sub(' ', text)


def keep_one_line(entry):
    """Text that reaches C{entry}, pasted or dropped, stays on one line: its
        values are saved to ini files, which keep one line (#4346, #4396)."""
    def on_changed(editable):
        text = editable.get_text()
        clean = one_line(text)
        if clean == text:
            return
        cursor = len(one_line(text[:editable.get_position()]))
        editable.set_text(clean)
        editable.set_position(cursor)
        # A paste places the cursor after its own change.
        GLib.idle_add(lambda: editable.set_position(cursor) and False)
    entry.connect('changed', on_changed)


def entry_value(entry):
    """What a one-line dialog field holds: its text without surrounding
        space, so a value of only spaces is empty."""
    return one_line(entry.get_text()).strip()
