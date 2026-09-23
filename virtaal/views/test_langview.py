#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from gi.repository import Gtk

from virtaal.models.langmodel import LanguageModel
from virtaal.views import baseview, langview
from virtaal.views.langview import LanguageView
from virtaal.views.widgets.langadddialog import LanguageAddDialog
from virtaal.views.widgets.langselectdialog import LanguageSelectDialog
from virtaal.views.widgets.popupmenubutton import PopupMenuButton


@pytest.fixture(autouse=True)
def _fresh_builder_cache(monkeypatch):
    # _create_dialogs() loads real widgets from virtaal.ui - a cached
    # builder would hand back the very same btn_add object (with every
    # previous test's own 'clicked' handler still connected to it)
    # across tests, so emitting 'clicked' here would also re-run a
    # stale handler bound to a different test's view, real add_dialog
    # included - whose real, unmocked run() blocks on a modal dialog.
    monkeypatch.setattr(baseview, '_builders', {})


def _fake_lang(name, code=None):
    return SimpleNamespace(name=name, code=code or name[:2].lower())


def _make_view(**controller_kwargs):
    view = LanguageView.__new__(LanguageView)
    main_window = Gtk.Window()
    status_bar = Gtk.Statusbar()
    main_controller = SimpleNamespace(
        view=SimpleNamespace(main_window=main_window, status_bar=status_bar),
        unit_controller=SimpleNamespace(view=SimpleNamespace(targets=[Gtk.TextView()])),
        show_error=lambda *a, **kw: None,
    )
    controller = SimpleNamespace(
        main_controller=main_controller,
        NUM_RECENT=5,
        recent_pairs=[],
        new_langs=[],
        **controller_kwargs,
    )
    view.controller = controller
    view.popupbutton = PopupMenuButton()  # update_recent_pairs()'s _init_menu() needs its real set_menu()
    view.menu = None
    view._popupbutton_fg_provider = None
    return view


def test_set_popupbutton_fg_accepts_a_colour():
    # A malformed generated CSS string raises Gtk.CssProvider's own
    # GLib.GError - this is really a check that the string built here
    # is valid CSS, not just that the call completes.
    view = LanguageView.__new__(LanguageView)
    view.popupbutton = Gtk.Button()
    view._popupbutton_fg_provider = None

    view._set_popupbutton_fg('#f66')


def test_set_popupbutton_fg_removes_its_previous_provider_on_a_later_call(monkeypatch):
    """notify_same_langs()/notify_diff_langs() toggle this on every
        cursor change - each call used to only ever add a new
        provider, accumulating one per toggle, never freed."""
    view = LanguageView.__new__(LanguageView)
    view.popupbutton = Gtk.Button()
    view._popupbutton_fg_provider = None

    removed = []
    style = view.popupbutton.get_style_context()
    monkeypatch.setattr(style, 'remove_provider', lambda provider: removed.append(provider))

    view._set_popupbutton_fg('#f66')
    first_provider = view._popupbutton_fg_provider
    view._set_popupbutton_fg(None)

    assert removed == [first_provider]
    assert view._popupbutton_fg_provider is None


# _get_display_string() #

def test_get_display_string_rtl(monkeypatch):
    monkeypatch.setattr(langview.platform, 'is_windows', False)
    view = LanguageView.__new__(LanguageView)
    view.popupbutton = Gtk.Button()
    view.popupbutton.set_direction(Gtk.TextDirection.RTL)

    result = view._get_display_string(_fake_lang('English'), _fake_lang('Arabic'))

    assert result == '‫English ← ‫Arabic'


def test_get_display_string_ltr_default(monkeypatch):
    monkeypatch.setattr(langview.platform, 'is_windows', False)
    view = LanguageView.__new__(LanguageView)
    view.popupbutton = Gtk.Button()
    view.popupbutton.set_direction(Gtk.TextDirection.LTR)

    result = view._get_display_string(_fake_lang('English'), _fake_lang('French'))

    assert result == 'English → French'


def test_get_display_string_uses_french_quotes_on_windows(monkeypatch):
    monkeypatch.setattr(langview.platform, 'is_windows', True)
    view = LanguageView.__new__(LanguageView)
    view.popupbutton = Gtk.Button()
    view.popupbutton.set_direction(Gtk.TextDirection.LTR)

    result = view._get_display_string(_fake_lang('English'), _fake_lang('French'))

    assert result == 'English » French'


# notify_same_langs() / notify_diff_langs() #

def test_notify_same_langs_highlights_the_button(monkeypatch):
    monkeypatch.setattr(langview.GLib, 'idle_add', lambda func: func())
    view = LanguageView.__new__(LanguageView)
    view.popupbutton = Gtk.Button()
    view._popupbutton_fg_provider = None

    view.notify_same_langs()

    assert view._popupbutton_fg_provider is not None


def test_notify_diff_langs_clears_the_highlight(monkeypatch):
    monkeypatch.setattr(langview.GLib, 'idle_add', lambda func: func())
    view = LanguageView.__new__(LanguageView)
    view.popupbutton = Gtk.Button()
    view._popupbutton_fg_provider = None
    view.notify_same_langs()

    view.notify_diff_langs()

    assert view._popupbutton_fg_provider is None


# show() / focus() #

def test_show_adds_the_button_to_the_status_bar():
    view = _make_view()

    view.show()

    assert view.popupbutton in view.controller.main_controller.view.status_bar.get_children()


def test_show_does_not_add_the_button_twice():
    view = _make_view()
    view.show()

    view.show()  # must not raise or add a duplicate

    assert view.controller.main_controller.view.status_bar.get_children().count(view.popupbutton) == 1


def test_focus_grabs_focus_on_the_popupbutton(monkeypatch):
    view = LanguageView.__new__(LanguageView)
    view.popupbutton = Gtk.Button()
    calls = []
    monkeypatch.setattr(view.popupbutton, 'grab_focus', lambda: calls.append(True))

    view.focus()

    assert calls == [True]


# update_recent_pairs() #

def test_update_recent_pairs_removes_a_previously_shown_item():
    view = _make_view()
    view.controller.recent_pairs = [(_fake_lang('English'), _fake_lang('French'))]
    view.update_recent_pairs()  # first call: adds the item to the menu

    view.controller.recent_pairs = []
    view.update_recent_pairs()  # second call: must remove it again

    assert view.recent_items[0].get_parent() is None


def test_update_recent_pairs_stops_at_num_recent():
    view = _make_view()
    view.controller.recent_pairs = [
        (_fake_lang('Lang%d' % i), _fake_lang('Other%d' % i)) for i in range(view.controller.NUM_RECENT + 2)
    ]

    view.update_recent_pairs()  # must not raise indexing past recent_items

    assert view.recent_items[view.controller.NUM_RECENT - 1].get_child().get_text()


# _create_dialogs() #

def test_create_dialogs_builds_both_dialogs():
    view = _make_view()

    view._create_dialogs()

    assert isinstance(view.select_dialog, LanguageSelectDialog)
    assert isinstance(view.add_dialog, LanguageAddDialog)
    assert view.add_dialog.dialog.get_transient_for() is view.select_dialog.dialog


def test_create_dialogs_wires_the_add_button_to_on_addlang_clicked(monkeypatch):
    calls = []
    monkeypatch.setattr(LanguageView, '_on_addlang_clicked', lambda self, button: calls.append(button))
    view = _make_view()

    view._create_dialogs()
    view.select_dialog.btn_add.emit('clicked')

    assert len(calls) == 1


# _on_addlang_clicked() #

def _fake_add_dialog(run_result=True, error=None, langname='Klingon', langcode='tlh', nplurals=2, plural='n != 1'):
    return SimpleNamespace(
        run=lambda: run_result,
        check_input_sanity=lambda: error,
        langname=langname,
        langcode=langcode,
        nplurals=nplurals,
        plural=plural,
    )


def _fake_select_dialog():
    return SimpleNamespace(
        dialog=Gtk.Window(),
        clear_langs=lambda: None,
        update_languages=lambda langs: None,
    )


def test_on_addlang_clicked_does_nothing_when_cancelled():
    view = _make_view()
    view.add_dialog = _fake_add_dialog(run_result=False)

    view._on_addlang_clicked(None)  # must not raise


def test_on_addlang_clicked_shows_an_error_for_invalid_input():
    view = _make_view()
    view.add_dialog = _fake_add_dialog(error='bad plural expression')
    view.select_dialog = _fake_select_dialog()
    errors = []
    view.controller.main_controller.show_error = lambda err, parent=None: errors.append(err)

    view._on_addlang_clicked(None)

    assert errors == ['bad plural expression']
    assert 'tlh' not in LanguageModel.languages


def test_on_addlang_clicked_rejects_an_already_used_code():
    LanguageModel('en')  # LanguageModel.languages populates lazily on first real use
    view = _make_view()
    view.add_dialog = _fake_add_dialog(langcode='en')  # already a real language

    with pytest.raises(Exception, match='already used'):
        view._on_addlang_clicked(None)


def test_on_addlang_clicked_registers_a_new_language():
    original_languages = dict(LanguageModel.languages)
    try:
        view = _make_view()
        view.add_dialog = _fake_add_dialog()
        view.select_dialog = _fake_select_dialog()

        view._on_addlang_clicked(None)

        assert LanguageModel.languages['tlh'] == ('Klingon', 2, 'n != 1')
        assert view.controller.new_langs == ['tlh']
    finally:
        LanguageModel.languages.clear()
        LanguageModel.languages.update(original_languages)


# _on_button_toggled() #

def test_on_button_toggled_ignores_a_deactivation():
    view = _make_view()
    view.update_recent_pairs = lambda: pytest.fail('should not be called')

    view._on_button_toggled(SimpleNamespace(get_active=lambda: False))


def test_on_button_toggled_adds_a_newly_detected_pair():
    view = _make_view()
    pair = (_fake_lang('English'), _fake_lang('French'))
    view.controller.get_detected_langs = lambda: pair
    calls = []
    view.update_recent_pairs = lambda: calls.append(True)

    view._on_button_toggled(SimpleNamespace(get_active=lambda: True))

    assert view.controller.recent_pairs == [pair]
    assert calls == [True]


def test_on_button_toggled_does_not_duplicate_an_already_recent_pair():
    view = _make_view()
    pair = (_fake_lang('English'), _fake_lang('French'))
    view.controller.get_detected_langs = lambda: pair
    view.controller.recent_pairs = [pair]
    view.update_recent_pairs = lambda: None

    view._on_button_toggled(SimpleNamespace(get_active=lambda: True))

    assert view.controller.recent_pairs == [pair]


def test_on_button_toggled_replaces_the_oldest_pair_once_full():
    view = _make_view()
    pair = (_fake_lang('English'), _fake_lang('French'))
    existing = [(_fake_lang('a'), _fake_lang('b')) for _ in range(5)]
    view.controller.recent_pairs = list(existing)
    view.controller.get_detected_langs = lambda: pair
    view.update_recent_pairs = lambda: None

    view._on_button_toggled(SimpleNamespace(get_active=lambda: True))

    assert view.controller.recent_pairs[-1] == pair
    assert len(view.controller.recent_pairs) == 5


def test_on_button_toggled_ignores_an_incomplete_detection():
    view = _make_view()
    view.controller.get_detected_langs = lambda: (_fake_lang('English'), None)
    calls = []
    view.update_recent_pairs = lambda: calls.append(True)

    view._on_button_toggled(SimpleNamespace(get_active=lambda: True))

    assert view.controller.recent_pairs == []
    assert calls == [True]


# _on_other_activated() #

def test_on_other_activated_creates_dialogs_when_missing():
    view = _make_view()
    created = []
    view._create_dialogs = lambda: (created.append(True), setattr(view, 'select_dialog', SimpleNamespace(
        run=lambda s, t: False, get_selected_source_lang=lambda: None, get_selected_target_lang=lambda: None)))[1]
    view.controller.set_language_pair = lambda *a: pytest.fail('should not be called')
    view.controller.source_lang = _fake_lang('English')
    view.controller.target_lang = _fake_lang('French')

    view._on_other_activated(None)

    assert created == [True]


def test_on_other_activated_sets_the_chosen_pair_when_confirmed():
    view = _make_view()
    chosen_source = _fake_lang('German')
    chosen_target = _fake_lang('Dutch')
    view.select_dialog = SimpleNamespace(
        run=lambda s, t: True,
        get_selected_source_lang=lambda: chosen_source,
        get_selected_target_lang=lambda: chosen_target,
    )
    view.controller.source_lang = _fake_lang('English')
    view.controller.target_lang = _fake_lang('French')
    calls = []
    view.controller.set_language_pair = lambda s, t: calls.append((s, t))
    focus_calls = []
    view.controller.main_controller.unit_controller.view.targets[0].grab_focus = lambda: focus_calls.append(True)

    view._on_other_activated(None)

    assert calls == [(chosen_source, chosen_target)]
    assert focus_calls == [True]


def test_on_other_activated_does_nothing_when_cancelled():
    view = _make_view()
    view.select_dialog = SimpleNamespace(
        run=lambda s, t: False,
        get_selected_source_lang=lambda: None,
        get_selected_target_lang=lambda: None,
    )
    view.controller.source_lang = _fake_lang('English')
    view.controller.target_lang = _fake_lang('French')
    view.controller.set_language_pair = lambda *a: pytest.fail('should not be called')

    view._on_other_activated(None)  # must not raise


# _on_pairitem_activated() #

def test_on_pairitem_activated_selects_that_pair():
    view = _make_view()
    pair = (_fake_lang('English'), _fake_lang('French'))
    view.controller.recent_pairs = [pair]
    view.recent_items = [SimpleNamespace(get_child=lambda: SimpleNamespace(get_text=lambda: '_1. English → French'))]
    calls = []
    view.controller.set_language_pair = lambda s, t: calls.append((s, t))
    focus_calls = []
    view.controller.main_controller.unit_controller.view.targets[0].grab_focus = lambda: focus_calls.append(True)

    view._on_pairitem_activated(None, 0)

    assert calls == [pair]
    assert focus_calls == [True]
