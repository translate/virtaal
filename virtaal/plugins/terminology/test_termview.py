#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from translate.storage.placeables import StringElem
from translate.storage.placeables.terminology import TerminologyPlaceable

from virtaal.common.signaltracker import SignalTracker
from virtaal.plugins.terminology import termview
from virtaal.plugins.terminology.termview import TerminologyGUIInfo, TerminologyView


def _term_elem(translations):
    elem = TerminologyPlaceable('drink')
    elem.translations = translations
    return elem


def test_terminology_gui_info_requires_a_terminology_placeable():
    with pytest.raises(AssertionError):
        TerminologyGUIInfo(StringElem('x'), textbox=None)


def test_get_insert_candidates_returns_none_for_a_single_translation():
    info = TerminologyGUIInfo(_term_elem(['drank']), textbox=None)

    assert info.get_insert_candidates() is None


def test_get_insert_candidates_lists_translations_in_sorted_order():
    # TerminologyPlaceable.translations comes from a set() in
    # translate-toolkit, so its order differs between runs (#3912).
    info = TerminologyGUIInfo(_term_elem(['lêer', 'dokument', 'argief']), textbox=None)

    assert info.get_insert_candidates() == ['argief', 'dokument', 'lêer']


class _FakeStyleContext:
    def __init__(self, found_theme_base):
        self._found_theme_base = found_theme_base

    def get_color(self, state):
        return 'fg-color'

    def lookup_color(self, name):
        return self._found_theme_base, 'theme-bg-color'

    def get_background_color(self, state):
        return 'fallback-bg-color'


class _FakeStyledWidget:
    def __init__(self, found_theme_base):
        self._ctx = _FakeStyleContext(found_theme_base)

    def get_style_context(self):
        return self._ctx


@pytest.fixture(autouse=True)
def _restore_gui_info_colors():
    # update_style() below sets these as CLASS attributes, shared
    # process-wide - restore the defaults so other tests aren't affected.
    yield
    TerminologyGUIInfo.fg = termview._default_fg
    TerminologyGUIInfo.bg = termview._default_bg


def test_update_style_uses_inverse_colors_when_the_theme_is_inverse(monkeypatch):
    monkeypatch.setattr(termview, 'is_inverse', lambda fg, bg: True)

    TerminologyGUIInfo.update_style(_FakeStyledWidget(found_theme_base=True))

    assert TerminologyGUIInfo.fg == termview._inverse_fg
    assert TerminologyGUIInfo.bg == termview._inverse_bg


def test_update_style_falls_back_to_default_colors_when_not_inverse(monkeypatch):
    monkeypatch.setattr(termview, 'is_inverse', lambda fg, bg: False)

    TerminologyGUIInfo.update_style(_FakeStyledWidget(found_theme_base=False))

    assert TerminologyGUIInfo.fg == termview._default_fg
    assert TerminologyGUIInfo.bg == termview._default_bg


def test_terminology_view_init_sets_up_controller_and_signal_tracker():
    controller = SimpleNamespace()

    view = TerminologyView(controller)

    assert view.controller is controller
    assert isinstance(view._signal_tracker, SignalTracker)


def test_destroy_disconnects_all_tracked_signals(monkeypatch):
    view = TerminologyView(SimpleNamespace())
    calls = []
    monkeypatch.setattr(view._signal_tracker, 'disconnect_all', lambda: calls.append(True))

    view.destroy()

    assert calls == [True]


def test_select_backends_delegates_to_backendselect(monkeypatch):
    controller = SimpleNamespace(
        main_controller='main-controller',
        plugin_controller='plugin-controller',
        config={'backends_dialog_width': 300},
    )
    view = TerminologyView(controller)
    calls = []
    monkeypatch.setattr('virtaal.views.backendselect.select_backends',
                         lambda *args, **kwargs: calls.append((args, kwargs)))
    parent = object()

    view.select_backends(parent)

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ('main-controller', 'plugin-controller', {'backends_dialog_width': 300}, 'basetermmodel')
    assert kwargs['parent'] is parent
    assert kwargs['size'] == (300, 300)
