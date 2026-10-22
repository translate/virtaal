#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""View > Fullscreen on Linux and Windows: the menu bar's menus move into
the app button and back."""

import sys

import pytest
from gi.repository import Gtk

from virtaal.common.platform import platform
from virtaal.test.test_scaffolding import TestScaffolding
from virtaal.views.mainview import MainView


def _labels(container):
    return [child.get_label() for child in container.get_children()]


class _Toggle:
    """View > Fullscreen as its handler sees it."""
    def __init__(self, active):
        self.active = active

    def get_active(self):
        return self.active


# On macOS the native menu bar holds the menus, so they never move.
@pytest.mark.skipif(sys.platform == 'darwin', reason='macOS keeps its menus in the native menu bar')
class TestFullscreenMenus(TestScaffolding):
    @pytest.fixture(autouse=True)
    def _view(self, monkeypatch):
        self.view = self.main_controller.view
        # The window manager's part: don't fullscreen a real window.
        self.window_states = []
        monkeypatch.setattr(self.view.main_window, 'fullscreen', lambda: self.window_states.append('fullscreen'))
        monkeypatch.setattr(self.view.main_window, 'unfullscreen', lambda: self.window_states.append('unfullscreen'))
        monkeypatch.setattr(platform, 'is_mac', False)
        self.menus = _labels(self.view.menubar)
        yield
        if self.view.menu_structure is self.view.app_menu:
            self._fullscreen(False)

    def _fullscreen(self, active):
        # Through this view's handler, not the menu item: every earlier test
        # class's view shares the cached builder's menu item and handles it too.
        self.view._on_fullscreen(_Toggle(active))

    def test_fullscreen_moves_the_menus_into_the_app_button(self):
        self._fullscreen(True)

        assert self.window_states == ['fullscreen']
        assert _labels(self.view.app_menu) == self.menus
        assert _labels(self.view.menubar) == []
        assert self.view.menu_structure is self.view.app_menu
        assert self.view.btn_app.get_visible()
        assert not self.view.menubar.get_visible()
        assert not self.view.status_bar.get_visible()

    def test_leaving_fullscreen_puts_the_menus_back_in_order(self):
        self._fullscreen(True)
        self._fullscreen(False)

        assert self.window_states == ['fullscreen', 'unfullscreen']
        assert _labels(self.view.menubar) == self.menus
        assert _labels(self.view.app_menu) == []
        assert self.view.menu_structure is self.view.menubar
        assert not self.view.btn_app.get_visible()
        assert self.view.menubar.get_visible()
        assert self.view.status_bar.get_visible()

    def test_fullscreen_again_reuses_the_app_menu(self):
        self._fullscreen(True)
        app_menu = self.view.app_menu
        self._fullscreen(False)

        self._fullscreen(True)

        assert self.view.app_menu is app_menu
        assert _labels(app_menu) == self.menus

    def test_a_moved_menu_keeps_its_signal_handlers(self):
        menu = self.view.menubar.get_children()[-1]
        activated = []
        handler = menu.connect('activate', lambda item: activated.append(item))
        try:
            self._fullscreen(True)

            assert self.view.app_menu.get_children()[-1] is menu
            menu.activate()
            assert activated == [menu]
        finally:
            menu.disconnect(handler)

    def test_the_app_button_pops_up_its_menu(self):
        self._fullscreen(True)

        self.view.btn_app.emit('pressed')

        assert self.view.app_menu.get_visible()
        self.view.app_menu.popdown()

    def test_macos_keeps_its_menus_in_place(self, monkeypatch):
        # They're in the native menu bar there.
        monkeypatch.setattr(platform, 'is_mac', True)

        self._fullscreen(True)

        assert self.window_states == ['fullscreen']
        assert _labels(self.view.menubar) == self.menus
        assert self.view.menu_structure is self.view.menubar


def test_move_menus_keeps_each_item_and_its_order():
    source, target = Gtk.MenuBar(), Gtk.Menu()
    items = [Gtk.MenuItem(label=label) for label in ('_File', '_Edit')]
    for item in items:
        source.append(item)

    MainView._move_menus(source, target)

    assert target.get_children() == items
    assert source.get_children() == []
