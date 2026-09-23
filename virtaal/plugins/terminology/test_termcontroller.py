#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from gi.repository import Gtk
from translate.storage.placeables import terminology

from virtaal.plugins.terminology import termcontroller
from virtaal.plugins.terminology.termcontroller import TerminologyController
from virtaal.plugins.terminology.termview import TerminologyGUIInfo
from virtaal.views import placeablesguiinfo


@pytest.fixture(autouse=True)
def _restore_element_gui_map():
    # __init__ inserts into this module-level, shared list.
    original = list(placeablesguiinfo.element_gui_map)
    yield
    placeablesguiinfo.element_gui_map[:] = original


class _FakePlaceablesController:
    def __init__(self):
        self.added_parsers = []
        self.removed_parsers = []
        self.non_target_placeables = []
        self.parsers = []
        self.connected = []

    def add_parsers(self, *parsers):
        self.added_parsers.extend(parsers)
        self.parsers.extend(parsers)

    def remove_parsers(self, parsers):
        self.removed_parsers.append(parsers)

    def connect(self, signal, handler):
        self.connected.append((signal, handler))
        return len(self.connected)


class _FakeSignalSource:
    def __init__(self):
        self.connected = []

    def connect(self, signal, handler):
        self.connected.append((signal, handler))
        return len(self.connected)


def _make_main_controller():
    return SimpleNamespace(
        placeables_controller=_FakePlaceablesController(),
        view=SimpleNamespace(main_window=Gtk.Window()),
        lang_controller=_FakeSignalSource(),
    )


def _make_controller(config=None):
    main_controller = _make_main_controller()
    controller = TerminologyController(main_controller, config=config)
    return controller, main_controller


def test_init_registers_the_terminology_parsers():
    controller, main_controller = _make_controller()

    assert list(terminology.parsers) == main_controller.placeables_controller.added_parsers
    assert terminology.TerminologyPlaceable in main_controller.placeables_controller.non_target_placeables


def test_init_connects_to_parsers_changed():
    controller, main_controller = _make_controller()

    signals = [s for s, _handler in main_controller.placeables_controller.connected]
    assert 'parsers-changed' in signals


def test_init_connects_lang_controller_signals():
    controller, main_controller = _make_controller()

    signals = [s for s, _handler in main_controller.lang_controller.connected]
    assert signals == ['source-lang-changed', 'target-lang-changed']


def test_init_registers_the_gui_info_for_terminology_placeables():
    controller, main_controller = _make_controller()

    assert (terminology.TerminologyPlaceable, TerminologyGUIInfo) in placeablesguiinfo.element_gui_map


def test_init_does_not_duplicate_the_gui_info_registration():
    placeablesguiinfo.element_gui_map.insert(0, (terminology.TerminologyPlaceable, TerminologyGUIInfo))
    before = list(placeablesguiinfo.element_gui_map)

    controller, main_controller = _make_controller()

    assert placeablesguiinfo.element_gui_map == before


def test_init_applies_the_default_style_immediately(monkeypatch):
    calls = []
    monkeypatch.setattr(TerminologyGUIInfo, 'update_style', classmethod(lambda cls, widget: calls.append(widget)))

    controller, main_controller = _make_controller()

    assert calls == [main_controller.view.main_window]


def test_init_disables_basetermmodel_by_default():
    controller, main_controller = _make_controller()

    assert controller.disabled_model_names == ['basetermmodel']


def test_init_appends_configured_disabled_models():
    controller, main_controller = _make_controller(config={'disabled_models': ['pontoon']})

    assert controller.disabled_model_names == ['basetermmodel', 'pontoon']


def test_init_configures_the_plugin_controller_for_the_terminology_backend():
    controller, main_controller = _make_controller()

    pc = controller.plugin_controller
    assert pc.PLUGIN_INTERFACE.__name__ == 'BaseTerminologyModel'
    assert pc.get_disabled_plugins() == ['basetermmodel']
    assert all(d.endswith('terminology/models') for d in pc.PLUGIN_DIRS)


def test_destroy_tears_down_the_view_and_plugins(monkeypatch):
    controller, main_controller = _make_controller()
    calls = []
    monkeypatch.setattr(controller.view, 'destroy', lambda: calls.append('view'))
    monkeypatch.setattr(controller.plugin_controller, 'shutdown', lambda: calls.append('plugins'))

    controller.destroy()

    assert calls == ['view', 'plugins']
    assert main_controller.placeables_controller.removed_parsers == [terminology.parsers]


def test_rescan_current_unit_does_nothing_without_a_unit_controller():
    controller, main_controller = _make_controller()

    controller.rescan_current_unit()  # must not raise


class _FakeElem:
    def __init__(self):
        self.removed_types = []

    def remove_type(self, cls):
        self.removed_types.append(cls)


class _FakeSource:
    def __init__(self):
        self.elem = _FakeElem()
        self.refreshed = []

    def refresh(self, update=False):
        self.refreshed.append(update)


def test_rescan_current_unit_reparses_every_source(monkeypatch):
    controller, main_controller = _make_controller()
    sources = [_FakeSource(), _FakeSource()]
    main_controller.unit_controller = SimpleNamespace(view=SimpleNamespace(sources=sources))
    parse_calls = []
    monkeypatch.setattr(termcontroller, 'elem_parse', lambda elem, parsers: parse_calls.append((elem, parsers)))

    controller.rescan_current_unit()

    for source in sources:
        assert source.elem.removed_types == [terminology.TerminologyPlaceable]
        assert source.refreshed == [True]
    assert len(parse_calls) == 2


def test_rescan_current_unit_stops_without_a_store_cursor():
    controller, main_controller = _make_controller()
    main_controller.unit_controller = SimpleNamespace(view=SimpleNamespace(sources=[]))
    main_controller.store_controller = SimpleNamespace(cursor=None)

    controller.rescan_current_unit()  # must not raise


def test_rescan_current_unit_refreshes_the_current_store_row():
    controller, main_controller = _make_controller()
    main_controller.unit_controller = SimpleNamespace(view=SimpleNamespace(sources=[]))
    calls = []
    treeview = SimpleNamespace(refresh_current_row=lambda: calls.append(True))
    main_controller.store_controller = SimpleNamespace(
        cursor=object(), view=SimpleNamespace(_treeview=treeview))

    controller.rescan_current_unit()

    assert calls == [True]


def test_on_placeables_changed_re_adds_a_missing_terminology_parser():
    controller, main_controller = _make_controller()
    main_controller.placeables_controller.parsers = []
    main_controller.placeables_controller.added_parsers = []

    controller._on_placeables_changed(main_controller.placeables_controller)

    assert main_controller.placeables_controller.added_parsers == list(terminology.parsers)


def test_on_placeables_changed_leaves_an_already_present_parser_alone():
    controller, main_controller = _make_controller()
    main_controller.placeables_controller.parsers = list(terminology.parsers)
    main_controller.placeables_controller.added_parsers = []

    controller._on_placeables_changed(main_controller.placeables_controller)

    assert main_controller.placeables_controller.added_parsers == []


def test_on_style_set_updates_the_terminology_gui_info(monkeypatch):
    controller, main_controller = _make_controller()
    calls = []
    monkeypatch.setattr(TerminologyGUIInfo, 'update_style', classmethod(lambda cls, widget: calls.append(widget)))

    controller._on_style_set(main_controller.view.main_window)

    assert calls == [main_controller.view.main_window]
