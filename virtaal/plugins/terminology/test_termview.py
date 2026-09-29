#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from gi.repository import Gtk
from translate.storage.placeables import StringElem
from translate.storage.placeables.terminology import TerminologyPlaceable

from virtaal.common.signaltracker import SignalTracker
from virtaal.plugins.terminology import termview
from virtaal.plugins.terminology.termview import (
    TerminologyCombo,
    TerminologyGUIInfo,
    TerminologyView,
)
from virtaal.views.widgets.textbox import TextBox


def _term_elem(translations):
    elem = TerminologyPlaceable('drink')
    elem.translations = translations
    return elem


def test_combo_handles_more_than_one_translation():
    # Only built when a placeable has more than one match, e.g. a
    # terminology entry with two definitions for the same source.
    TerminologyCombo(_term_elem(['drank', 'dryf']))


def test_combo_lists_translations_in_sorted_order():
    # TerminologyPlaceable.translations comes from a set() in
    # translate-toolkit, so its order differs between runs (#3912).
    combo = TerminologyCombo(_term_elem(['lêer', 'dokument', 'argief']))

    assert [row[0] for row in combo._model] == ['argief', 'dokument', 'lêer']


def test_get_termcombo_css_provider_is_cached():
    termview._termcombo_css_provider = None
    try:
        provider = termview._get_termcombo_css_provider()

        assert termview._get_termcombo_css_provider() is provider
    finally:
        termview._termcombo_css_provider = None


def test_combo_chrome_is_hidden_so_only_the_popup_list_is_visible():
    # The combo is meant to stay invisible until it pops up - a full-size
    # GTK3 button+arrow here means it's back to showing chrome inline.
    combo = TerminologyCombo(_term_elem(['drank', 'dryf']))
    window = Gtk.OffscreenWindow()
    window.add(combo)
    window.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()

    _, natural_size = combo.get_preferred_size()

    # GTK3's default combobox chrome (button padding/border + arrow icon)
    # is roughly 75x34 - a hidden-chrome combo should be much smaller.
    assert natural_size.width < 50
    assert natural_size.height < 25


def test_terminology_gui_info_requires_a_terminology_placeable():
    with pytest.raises(AssertionError):
        TerminologyGUIInfo(StringElem('x'), textbox=None)


def test_get_insert_widget_returns_none_for_a_single_translation():
    info = TerminologyGUIInfo(_term_elem(['drank']), textbox=None)

    assert info.get_insert_widget() is None


def test_get_insert_widget_returns_a_combo_for_multiple_translations():
    info = TerminologyGUIInfo(_term_elem(['drank', 'dryf']), textbox=None)

    widget = info.get_insert_widget()

    assert isinstance(widget, TerminologyCombo)


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


class _FakeUndoController:
    """Just enough of UndoController for insert_selected()'s
        record_start()/record_stop() calls."""
    def __init__(self):
        from virtaal.models.undomodel import UndoModel
        self.model = UndoModel(self)
        self.record_start_calls = 0
        self.record_stop_calls = 0

    def record_start(self):
        self.record_start_calls += 1
        self.model.record_start()

    def record_stop(self):
        self.record_stop_calls += 1
        self.model.record_stop()


def _make_combo_in_textview(translations):
    # insert_selected() relies on the real TextBox's own 'changed' signal
    # and refresh_cursor_pos attribute - a plain Gtk.TextView has neither.
    combo = TerminologyCombo(_term_elem(translations))
    window = Gtk.Window()
    main_controller = SimpleNamespace(placeables_controller=object(), undo_controller=_FakeUndoController())
    textview = TextBox(main_controller)
    window.add(textview)
    buffer = textview.get_buffer()
    anchor = buffer.create_child_anchor(buffer.get_start_iter())
    textview.add_child_at_anchor(combo, anchor)
    window.show_all()
    return combo, textview, buffer


def _buffer_text(buffer):
    return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)


def test_inserted_records_the_offset_focuses_and_pops_up(monkeypatch):
    combo, textview, buffer = _make_combo_in_textview(['drank', 'dryf'])
    popup_calls = []
    monkeypatch.setattr(combo, 'popup', lambda: popup_calls.append(True))

    combo.inserted(buffer.get_start_iter(), None)

    assert combo.insert_offset == 0
    assert popup_calls == [True]


def test_insert_selected_inserts_the_chosen_translation():
    combo, textview, buffer = _make_combo_in_textview(['drank', 'dryf'])
    combo.insert_offset = 0
    combo.set_active(1)  # 'dryf'

    combo.insert_selected()

    assert _buffer_text(buffer) == 'dryf'
    assert combo.get_parent() is None
    assert textview.is_focus()


def test_insert_selected_groups_the_anchor_delete_and_insert_into_one_undo_step():
    combo, textview, buffer = _make_combo_in_textview(['drank', 'dryf'])
    combo.insert_offset = 0
    combo.set_active(1)  # 'dryf'

    combo.insert_selected()

    undo_controller = textview.undo_controller
    assert undo_controller.record_start_calls == 1
    assert undo_controller.record_stop_calls == 1
    assert not undo_controller.model.recording  # closed, not left open


def test_insert_selected_does_nothing_when_no_translation_is_selected():
    combo, textview, buffer = _make_combo_in_textview(['drank', 'dryf'])
    combo.insert_offset = 0

    combo.insert_selected()

    assert _buffer_text(buffer) == ''
    assert combo.get_parent() is None


def test_insert_selected_skips_buffer_edits_when_never_actually_inserted():
    combo, textview, buffer = _make_combo_in_textview(['drank', 'dryf'])
    combo.insert_offset = -1
    combo.set_active(0)

    combo.insert_selected()  # must not raise

    assert combo.get_parent() is None


def test_on_selection_done_calls_insert_selected(monkeypatch):
    combo, textview, buffer = _make_combo_in_textview(['drank', 'dryf'])
    calls = []
    monkeypatch.setattr(combo, 'insert_selected', lambda: calls.append(True))

    combo._on_selection_done(combo.menu)

    assert calls == [True]


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
