#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk

from virtaal.views.widgets import wayland


def test_is_wayland_reads_the_display_type(monkeypatch):
    display = SimpleNamespace(__gtype__=SimpleNamespace(name='GdkWaylandDisplay'))
    monkeypatch.setattr(wayland.Gdk.Display, 'get_default', staticmethod(lambda: display))
    assert wayland.is_wayland()

    display.__gtype__.name = 'GdkX11Display'
    assert not wayland.is_wayland()


def test_is_wayland_without_a_display(monkeypatch):
    monkeypatch.setattr(wayland.Gdk.Display, 'get_default', staticmethod(lambda: None))
    assert not wayland.is_wayland()


def test_set_popup_parent_only_on_wayland(monkeypatch):
    parent = Gtk.Window()
    popup = Gtk.Window(type=Gtk.WindowType.POPUP)

    monkeypatch.setattr(wayland, 'is_wayland', lambda: False)
    wayland.set_popup_parent(popup, parent)
    assert popup.get_transient_for() is None

    monkeypatch.setattr(wayland, 'is_wayland', lambda: True)
    wayland.set_popup_parent(popup, parent)
    assert popup.get_transient_for() is parent
