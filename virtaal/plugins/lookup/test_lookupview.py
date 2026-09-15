#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk, Pango

from virtaal.plugins.lookup.lookupview import LookupView


class _FakeBuffer:
    def __init__(self, text):
        self._text = text

    def get_has_selection(self):
        return bool(self._text)

    def get_selection_bounds(self):
        return (0, len(self._text), False)

    def get_text(self, *args, **kwargs):
        return self._text


class _FakeTextbox:
    def __init__(self, text, role='source'):
        self.buffer = _FakeBuffer(text)
        self.role = role


class _FakeLang:
    code = 'en'


class _FakeLangController:
    source_lang = _FakeLang()
    target_lang = _FakeLang()


class _FakeModel:
    def create_menu_items(self, *args):
        return [Gtk.MenuItem(label='Google')]


class _FakePluginController:
    def __init__(self, plugins):
        self.plugins = plugins


class _FakeController:
    def __init__(self, plugins):
        self.plugin_controller = _FakePluginController(plugins)


def _make_view(plugins):
    view = LookupView.__new__(LookupView)
    view.controller = _FakeController(plugins)
    view.lang_controller = _FakeLangController()
    return view


def test_populate_popup_does_nothing_without_a_selection():
    view = _make_view({'weblookup': _FakeModel()})
    menu = Gtk.Menu()

    view._on_populate_popup(_FakeTextbox(''), menu)

    assert menu.get_children() == []


def test_populate_popup_ellipsizes_a_long_selection():
    view = _make_view({'weblookup': _FakeModel()})
    menu = Gtk.Menu()

    view._on_populate_popup(_FakeTextbox('a' * 60), menu)

    item = next(i for i in menu.get_children() if isinstance(i, Gtk.MenuItem) and i.get_submenu())
    assert item.get_label() == 'Look-up "%s"' % ('a' * 60)
    label_widget = item.get_child()
    assert label_widget.get_ellipsize() == Pango.EllipsizeMode.MIDDLE
    assert label_widget.get_max_width_chars() == 40
