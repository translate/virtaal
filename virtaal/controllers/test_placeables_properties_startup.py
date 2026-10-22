#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""PlaceablesController and PropertiesController as the app starts them."""

import pytest
from gi.repository import Gtk
from translate.storage.placeables import StringElem, general

from virtaal.common import pan_app
from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.controllers.propertiescontroller import PropertiesController
from virtaal.test.test_scaffolding import TestScaffolding
from virtaal.views import placeablesguiinfo
from virtaal.views.propertiesview import PropertiesView

XML_TAG = general.XMLTagPlaceable.parse
ALT_ATTR = general.AltAttrPlaceable.parse


def _types(elem):
    return [type(e).__name__ for e in elem.depth_first()]


class TestPlaceablesAndProperties(TestScaffolding):
    def setup_class(self):
        TestScaffolding.setup_class(self)
        self.placeables = PlaceablesController(self.main_controller)
        self.properties = PropertiesController(self.main_controller)

    @pytest.fixture(autouse=True)
    def _state(self, monkeypatch):
        # Never the real config: _on_quit() writes here.
        monkeypatch.setattr(pan_app.settings, 'placeable_state', {})
        parsers = list(self.placeables.parsers)
        self.changes = []
        handler = self.placeables.connect('parsers-changed', lambda controller: self.changes.append(True))
        yield
        self.placeables.disconnect(handler)
        self.placeables.parsers = parsers

    # PlaceablesController

    def test_add_parsers_refuses_something_that_is_not_a_parser(self):
        before = list(self.placeables.parsers)

        with pytest.raises(TypeError):
            self.placeables.add_parsers(XML_TAG, 'not a parser')

        assert self.placeables.parsers == before
        assert self.changes == []

    def test_apply_parsers_parses_a_single_element_in_place(self):
        elem = StringElem('Open <b>%s</b>')

        assert self.placeables.apply_parsers(elem) == [elem]
        assert 'XMLTagPlaceable' in _types(elem)
        assert 'PythonFormattingPlaceable' in _types(elem)

    def test_apply_parsers_uses_only_the_parsers_given(self):
        elems = [StringElem('Open <b>%s</b>'), StringElem('<i>now</i>')]

        assert self.placeables.apply_parsers(elems, [XML_TAG]) is elems
        assert 'PythonFormattingPlaceable' not in _types(elems[0])
        assert 'XMLTagPlaceable' in _types(elems[1])

    def test_get_gui_info_refuses_a_plain_string(self):
        with pytest.raises(ValueError):
            self.placeables.get_gui_info('Open')

    def test_get_gui_info_falls_back_to_the_plain_gui(self):
        assert self.placeables.get_gui_info(StringElem('Open')) is placeablesguiinfo.StringElemGUI

    def test_remove_parsers_removes_them_and_signals_once(self):
        self.placeables.remove_parsers(XML_TAG, ALT_ATTR)

        assert XML_TAG not in self.placeables.parsers
        assert self.changes == [True]

    def test_remove_parsers_without_a_change_does_not_signal(self):
        self.placeables.remove_parsers(XML_TAG)
        self.changes.clear()

        self.placeables.remove_parsers(XML_TAG)

        assert self.changes == []

    def test_quitting_saves_a_disabled_placeable(self):
        self.placeables.remove_parsers(XML_TAG)

        self.placeables._on_quit(self.main_controller)

        assert pan_app.settings.placeable_state['xmltagplaceable'] == 'disabled'

    def test_quitting_saves_a_placeable_enabled_again(self):
        # Saved as disabled at the last quit, enabled since.
        pan_app.settings.placeable_state['xmltagplaceable'] = 'disabled'
        self.placeables.add_parsers(XML_TAG)

        self.placeables._on_quit(self.main_controller)

        assert pan_app.settings.placeable_state['xmltagplaceable'] == 'enabled'

    def test_quitting_leaves_enabled_placeables_unsaved_until_one_is_disabled(self):
        self.placeables.add_parsers(XML_TAG)

        self.placeables._on_quit(self.main_controller)

        assert 'xmltagplaceable' not in pan_app.settings.placeable_state

    # PropertiesController

    def test_properties_starts_with_its_view(self):
        assert isinstance(self.properties.view, PropertiesView)
        assert self.properties.view.controller is self.properties

    def test_file_properties_opens_the_properties_dialog(self, monkeypatch):
        shown = []
        monkeypatch.setattr(self.properties.view, 'show', lambda: shown.append(True))
        mnu_properties = self.main_controller.view.gui.get_object('mnu_properties')

        mnu_properties.activate()

        assert shown == [True]
        assert mnu_properties.get_accel_path() == '<Virtaal>/File/Properties'
        found, key = Gtk.AccelMap.lookup_entry('<Virtaal>/File/Properties')
        assert found
