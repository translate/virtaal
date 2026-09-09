#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.views.widgets.util import forall_widgets, get_children


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
