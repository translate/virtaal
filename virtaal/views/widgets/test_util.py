#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gdk, Gtk

from virtaal.views.widgets.util import (
    entry_value,
    forall_widgets,
    get_children,
    keep_one_line,
    one_line,
)


def test_get_children_default_is_empty():
    assert get_children(Gtk.Label(label='leaf')) == []


def test_get_children_container_returns_its_children():
    box = Gtk.Box()
    child = Gtk.Label(label='child')
    box.add(child)

    assert get_children(box) == [child]


def test_forall_widgets_visits_parent_then_children():
    box = Gtk.Box()
    child = Gtk.Label(label='child')
    box.add(child)

    visited = []
    forall_widgets(visited.append, box)

    assert visited == [box, child]


@pytest.mark.parametrize('text, expected', [
    ('a\r\nb', 'a b'), ('a\rb', 'a b'), ('a\nb', 'a b'), ('a\tb', 'a b'),
    ('a\n\n\tb', 'a b'), ('a\u2028b', 'a b'), ('a  b', 'a  b'), ('# hash', '# hash'),
])
def test_one_line(text, expected):
    assert one_line(text) == expected


def _one_line_entry():
    entry = Gtk.Entry()
    keep_one_line(entry)
    window = Gtk.Window()
    window.add(entry)
    window.show_all()
    return entry, window


def test_keep_one_line_turns_inserted_line_breaks_into_spaces():
    # #4346, #4396: a newline or CR saved to an ini file doesn't come back as it was.
    entry, window = _one_line_entry()
    try:
        entry.set_text('Ann ')
        entry.insert_text('Vertaler\r\n# Team\tAf', len('Ann '))

        assert entry.get_text() == 'Ann Vertaler # Team Af'
    finally:
        window.destroy()


def test_keep_one_line_applies_to_a_paste():
    entry, window = _one_line_entry()
    try:
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text('one\ntwo', -1)
        entry.grab_focus()
        entry.emit('paste-clipboard')
        while Gtk.events_pending():
            Gtk.main_iteration()

        assert entry.get_text() == 'one two'
        assert entry.get_position() == len('one two')
    finally:
        window.destroy()


def test_keep_one_line_leaves_plain_text_alone():
    entry, window = _one_line_entry()
    try:
        entry.insert_text('  Ann ; Vertaler  ', 0)

        assert entry.get_text() == '  Ann ; Vertaler  '
    finally:
        window.destroy()


@pytest.mark.parametrize('text, expected', [('  Ann  ', 'Ann'), ('\u00a0', ''), ('\t \n', ''), ('a\nb', 'a b')])
def test_entry_value_is_trimmed_and_on_one_line(text, expected):
    entry = Gtk.Entry()
    entry.set_text(text)

    assert entry_value(entry) == expected
