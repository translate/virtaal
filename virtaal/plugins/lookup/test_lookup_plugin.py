#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The look-up plug-in started the way Virtaal starts it: through its
own constructor, against a real main controller and unit view."""

import pytest
from gi.repository import GLib, Gtk

from virtaal.common import pan_app
from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.plugins.lookup import Plugin
from virtaal.plugins.lookup.models import thesaurus
from virtaal.test.test_scaffolding import TestScaffolding
from virtaal.views.widgets.selectdialog import SelectDialog


class _OfflineManifest:
    """The thesaurus model checks the asset manifest at start-up and on
        every language change."""
    checks = []

    def ensure_fresh(self, on_done=None):
        _OfflineManifest.checks.append(on_done)

    def get(self, resource_type, locale_code):
        return None

    def has_data(self):
        return True


def _labels(menu):
    return [i.get_label() for i in menu.get_children() if isinstance(i, Gtk.MenuItem) and i.get_label()]


def _lookup_submenu(menu):
    item = next((i for i in menu.get_children() if (i.get_label() or '').startswith('Look-up "')), None)
    return item and _labels(item.get_submenu())


class TestLookupPlugin(TestScaffolding):

    def setup_class(self):
        TestScaffolding.setup_class(self)
        # Without it no text is rendered into the textboxes.
        PlaceablesController(self.main_controller)

    @pytest.fixture(autouse=True)
    def _offline(self, monkeypatch, tmp_path):
        # Pumping the real main loop hangs in this suite: models are
        # loaded from idle callbacks, so run those at once.
        monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: func(*args))
        monkeypatch.setattr(pan_app, 'get_config_dir', lambda: str(tmp_path))
        monkeypatch.setattr(thesaurus, 'AssetManifest', _OfflineManifest)
        _OfflineManifest.checks = []
        self.config_dir = tmp_path

    def _show_unit(self):
        return self.unit_controller.load_unit(self.trans_store.units[1])

    def _context_menu(self, textbox, word):
        text = textbox.get_text()
        start = text.index(word)
        textbox.buffer.select_range(
            textbox.buffer.get_iter_at_offset(start), textbox.buffer.get_iter_at_offset(start + len(word)))
        menu = Gtk.Menu()
        textbox.emit('populate-popup', menu)
        return menu

    # Runs first in the class, before any unit is shown.
    def test_started_before_the_textboxes_exist_it_adds_to_their_context_menus(self):
        assert self.unit_controller.view.sources == []
        plugin = Plugin('lookup', self.main_controller)
        try:
            source = self._show_unit().sources[0]

            menu = self._context_menu(source, 'directory')

            assert _lookup_submenu(menu) == ['Google', 'Wikipedia', 'Wiktionary']
            assert any('thesaurus' in label for label in _labels(menu))
        finally:
            plugin.destroy()

        assert _lookup_submenu(self._context_menu(source, 'directory')) is None

    def test_started_once_the_textboxes_exist_it_adds_to_their_context_menus(self):
        source = self._show_unit().sources[0]
        plugin = Plugin('lookup', self.main_controller)
        try:
            menu = self._context_menu(source, 'directory')
        finally:
            plugin.destroy()

        assert _lookup_submenu(menu) == ['Google', 'Wikipedia', 'Wiktionary']

    def test_a_service_disabled_in_the_chooser_stays_disabled_at_the_next_start(self, monkeypatch):
        shown = []

        def choose(dialog, items=None, parent=None):
            shown.append((dialog.dialog.get_title(), sorted(i['name'] for i in items)))
            dialog.emit('item-disabled', next(i for i in items if i['data']['internal_name'] == 'weblookup'))
        monkeypatch.setattr(SelectDialog, 'run', choose)
        plugin = Plugin('lookup', self.main_controller)
        try:
            plugin.configure(self.main_controller.view.main_window)
        finally:
            plugin.destroy()

        assert shown == [('Select Look-up Services', ['Thesaurus', 'Web Look-up'])]
        plugin = Plugin('lookup', self.main_controller)
        try:
            assert sorted(plugin.controller.plugin_controller.plugins) == ['thesaurus']
            assert _lookup_submenu(self._context_menu(self._show_unit().sources[0], 'directory')) is None
        finally:
            plugin.destroy()

    def test_with_every_service_disabled_the_context_menu_is_unchanged(self):
        (self.config_dir / 'plugins.ini').write_text('[lookup]\ndisabled_models = weblookup,thesaurus\n')
        source = self._show_unit().sources[0]
        before = _labels(self._context_menu(source, 'directory'))
        plugin = Plugin('lookup', self.main_controller)
        try:
            menu = self._context_menu(source, 'directory')
        finally:
            plugin.destroy()

        assert plugin.controller.plugin_controller.plugins == {}
        assert _labels(menu) == before
        assert len(menu.get_children()) == len(before)
