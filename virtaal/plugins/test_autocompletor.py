#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from gi.repository import GLib, Gtk

from virtaal.plugins.autocompletor import AutoCompletor, Plugin
from virtaal.views.widgets.textbox import TextBox


def _ac(comp_len=AutoCompletor.DEFAULT_COMPLETION_LENGTH):
    return AutoCompletor(main_controller=None, comp_len=comp_len)


class _Fake:
    """A plain, hashable stand-in for a widget - unlike SimpleNamespace,
    whose own __eq__ makes it unusable as a dict key (autocompletor
    keys _textbox_insert_ids by the widget itself)."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# isusable() #

def test_isusable_rejects_a_word_at_the_length_boundary():
    ac = _ac(comp_len=4)
    assert ac.isusable('123456') is False  # len 6 == comp_len + 2


def test_isusable_accepts_a_word_just_over_the_boundary():
    ac = _ac(comp_len=4)
    assert ac.isusable('1234567') is True  # len 7 > comp_len + 2


# add_words() / _update_word_list() #

def test_add_words_filters_out_words_too_short_to_be_usable():
    ac = _ac(comp_len=4)
    ac.add_words(['short', 'alongenoughword'])

    assert 'short' not in ac._word_list
    assert 'alongenoughword' in ac._word_list


def test_add_words_orders_the_word_list_by_frequency_descending():
    ac = _ac(comp_len=1)
    ac.add_words(['rare', 'common', 'common', 'common', 'medium', 'medium'])

    assert ac._word_list == ['common', 'medium', 'rare']


def test_add_words_with_update_false_defers_rebuilding_the_word_list():
    ac = _ac(comp_len=1)
    ac.add_words(['alongword'], update=False)

    assert 'alongword' in ac._word_freq
    assert ac._word_list == []


def test_add_words_accumulates_frequency_across_calls():
    ac = _ac(comp_len=1)
    ac.add_words(['word'])
    ac.add_words(['word'])

    assert ac._word_freq['word'] == 2


# add_words_from_units() #

def test_add_words_from_units_splits_target_text_into_words():
    ac = _ac(comp_len=1)
    unit = SimpleNamespace(target='hello world')

    ac.add_words_from_units([unit])

    assert 'hello' in ac._word_list
    assert 'world' in ac._word_list


def test_add_words_from_units_skips_a_unit_with_no_target():
    ac = _ac(comp_len=1)
    unit = SimpleNamespace(target='')

    ac.add_words_from_units([unit])  # must not raise

    assert ac._word_list == []


# autocomplete() #

def test_autocomplete_finds_the_first_matching_prefix_by_frequency():
    ac = _ac(comp_len=1)
    ac.add_words(['helsinki', 'helsinki', 'hello'])  # helsinki more frequent

    word, suffix = ac.autocomplete('hel')

    assert word == 'helsinki'
    assert suffix == 'sinki'


def test_autocomplete_returns_none_and_empty_suffix_for_no_match():
    ac = _ac(comp_len=1)
    ac.add_words(['hello'])

    word, suffix = ac.autocomplete('xyz')

    assert word is None
    assert suffix == ''


# clear_words() #

def test_clear_words_resets_frequency_and_list():
    ac = _ac(comp_len=1)
    ac.add_words(['hello'])

    ac.clear_words()

    assert ac._word_list == []
    assert ac._word_freq['hello'] == 0


# remove_words() - normal (in-sync) case; the desync/exception case
# fixed in #3637 is covered separately below.

def test_remove_words_removes_a_word_present_in_both_structures():
    ac = _ac(comp_len=1)
    ac.add_words(['hello', 'world'])

    ac.remove_words('hello')

    assert 'hello' not in ac._word_list
    assert 'world' in ac._word_list


def test_remove_words_accepts_a_list_of_words():
    ac = _ac(comp_len=1)
    ac.add_words(['hello', 'world', 'kept'])

    ac.remove_words(['hello', 'world'])

    assert ac._word_list == ['kept']


def test_remove_words_tolerates_a_word_freq_entry_never_synced_to_word_list():
    """add_words(update=False) - used internally by add_words_from_units()'s
        per-unit loop - populates _word_freq without rebuilding _word_list,
        so the two can legitimately disagree about a given word. Removing
        such a word used to raise an uncaught ValueError from
        _word_list.remove() (only KeyError was ever caught)."""
    ac = _ac(comp_len=1)
    ac.add_words(['itisalongword'], update=False)
    assert 'itisalongword' in ac._word_freq
    assert 'itisalongword' not in ac._word_list

    ac.remove_words('itisalongword')  # must not raise

    assert 'itisalongword' not in ac._word_freq


def test_remove_words_tolerates_the_same_desync_for_a_list_of_words():
    ac = _ac(comp_len=1)
    ac.add_words(['itisalongword'], update=False)

    ac.remove_words(['itisalongword', 'nosuchword'])  # must not raise


def test_add_words_from_units_stops_after_reaching_max_words():
    ac = _ac(comp_len=1)
    ac.MAX_WORDS = 1
    units = [
        SimpleNamespace(target='firstword'),
        SimpleNamespace(target='secondword'),
        SimpleNamespace(target='thirdword'),
    ]

    ac.add_words_from_units(units)

    assert 'firstword' in ac._word_list
    assert 'secondword' in ac._word_list
    assert 'thirdword' not in ac._word_list


# widget registration #

def _fake_widget():
    """A TextBox type tag (for isinstance checks in add_widget()/
        remove_widget()) with its connect()/disconnect() overridden -
        avoids constructing a real, GTK-widget-backed TextBox."""
    calls = []
    widget = TextBox.__new__(TextBox)
    widget.connect = lambda signal, handler: calls.append(('connect', signal)) or 'sigid'
    widget.disconnect = lambda sig_id: calls.append(('disconnect', sig_id))
    return widget, calls


def test_add_widget_ignores_an_already_registered_widget():
    ac = _ac()
    widget = object()
    ac.widgets.add(widget)

    ac.add_widget(widget)  # must not raise despite not being a TextBox


def test_add_widget_rejects_an_unsupported_widget_type():
    ac = _ac()

    with pytest.raises(ValueError):
        ac.add_widget(object())


def test_add_widget_dispatches_a_textbox_to_add_text_box(monkeypatch):
    ac = _ac()
    added = []
    monkeypatch.setattr(ac, '_add_text_box', added.append)
    textbox = TextBox.__new__(TextBox)  # a type tag only - _add_text_box is stubbed

    ac.add_widget(textbox)

    assert added == [textbox]


def test_add_text_box_connects_and_registers_the_widget():
    ac = _ac()
    widget, calls = _fake_widget()

    ac._add_text_box(widget)

    assert calls == [('connect', 'text-inserted')]
    assert widget in ac.widgets
    assert ac._textbox_insert_ids[widget] == 'sigid'


def test_remove_widget_ignores_a_widget_that_was_never_added():
    ac = _ac()

    ac.remove_widget(object())  # must not raise


def test_remove_widget_disconnects_a_registered_textbox():
    ac = _ac()
    widget, calls = _fake_widget()
    ac._add_text_box(widget)

    ac.remove_widget(widget)

    assert ('disconnect', 'sigid') in calls
    assert widget not in ac.widgets


def test_remove_textbox_does_nothing_before_any_widget_was_ever_added():
    ac = _ac()

    ac._remove_textbox(object())  # must not raise


def test_clear_widgets_removes_every_registered_widget():
    ac = _ac()
    w1, _ = _fake_widget()
    w2, _ = _fake_widget()
    ac._add_text_box(w1)
    ac._add_text_box(w2)

    ac.clear_widgets()

    assert ac.widgets == set()


# _on_insert_text() - the actual autocomplete-while-typing logic #

def _insert_text_box(prefix, suffix, buffer_text=None):
    """A fake textbox whose get_text() mirrors TextBox's own
        get_text(start, end)/get_text(start) shapes, backed by a real
        Gtk.TextBuffer for the final selection check."""
    buf = Gtk.TextBuffer()
    buf.set_text(buffer_text if buffer_text is not None else (prefix + suffix))
    calls = []
    textbox = _Fake(
        get_text=lambda start=0, end=None: (prefix if end is not None else suffix),
        buffer=buf,
        handler_block=lambda hid: calls.append(('block', hid)),
        handler_unblock=lambda hid: calls.append(('unblock', hid)),
    )
    return textbox, calls


def test_on_insert_text_ignores_a_non_string_insertion():
    ac = _ac(comp_len=1)

    ac._on_insert_text(SimpleNamespace(), text=object(), offset=0, elem=None)  # must not raise


def test_on_insert_text_ignores_a_separator_character():
    ac = _ac(comp_len=1)

    ac._on_insert_text(SimpleNamespace(), text=' ', offset=0, elem=None)  # must not raise


def test_on_insert_text_ignores_a_multi_character_insertion():
    ac = _ac(comp_len=1)

    ac._on_insert_text(SimpleNamespace(), text='word', offset=0, elem=None)  # a paste, not typing


def test_on_insert_text_does_not_suggest_in_the_middle_of_a_word(monkeypatch):
    ac = _ac(comp_len=1)
    ac.add_words(['helsinki'])
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add',
                         lambda *a, **k: pytest.fail('must not suggest mid-word'))
    textbox, _ = _insert_text_box(prefix='hel', suffix='sinki')

    ac._on_insert_text(textbox, text='l', offset=2, elem=None)


def test_on_insert_text_does_not_suggest_a_word_shorter_than_comp_len(monkeypatch):
    ac = _ac(comp_len=10)
    ac.add_words(['helsinki'])
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add',
                         lambda *a, **k: pytest.fail('must not suggest a too-short word'))
    textbox, _ = _insert_text_box(prefix='hel', suffix='')

    ac._on_insert_text(textbox, text='l', offset=2, elem=None)


def test_on_insert_text_does_not_suggest_when_the_word_is_already_complete(monkeypatch):
    ac = _ac(comp_len=1)
    ac.add_words(['hello'])
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add',
                         lambda *a, **k: pytest.fail('must not suggest an exact match'))
    textbox, _ = _insert_text_box(prefix='hell', suffix='')

    ac._on_insert_text(textbox, text='o', offset=4, elem=None)


def test_on_insert_text_does_not_suggest_without_a_matching_word(monkeypatch):
    ac = _ac(comp_len=1)
    ac.add_words(['xyzxyzxyz'])
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add',
                         lambda *a, **k: pytest.fail('must not suggest without a match'))
    textbox, _ = _insert_text_box(prefix='hel', suffix='')

    ac._on_insert_text(textbox, text='l', offset=2, elem=None)


def test_on_insert_text_schedules_and_applies_a_deferred_suggestion(monkeypatch):
    ac = _ac(comp_len=1)
    ac.add_words(['helsinki'])
    scheduled = []
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add',
                         lambda f, priority=None: scheduled.append((f, priority)))
    textbox, calls = _insert_text_box(prefix='he', suffix='', buffer_text='helsinki')
    ac._textbox_insert_ids = {textbox: 'sigid'}

    ac._on_insert_text(textbox, text='l', offset=2, elem=None)

    assert len(scheduled) == 1
    func, priority = scheduled[0]
    assert priority == GLib.PRIORITY_HIGH

    assert func() is False  # runs the deferred suggestion for real
    assert textbox.suggestion == {'text': 'sinki', 'offset': 3}
    assert calls == [('block', 'sigid'), ('unblock', 'sigid')]
    start, end = textbox.buffer.get_selection_bounds()
    assert (start.get_offset(), end.get_offset()) == (3, 8)


# Plugin - completely untested until now #

def _plugin_main_controller(store=None, targets=None):
    calls = []
    store_controller = SimpleNamespace(
        connect=lambda signal, handler: calls.append((signal, handler)) or 'store-sig',
        disconnect=lambda sig_id: calls.append(('disconnect', sig_id)),
        get_store=lambda: store,
    )
    unitview = SimpleNamespace(
        targets=targets or [],
        connect=lambda signal, handler: calls.append((signal, handler)) or 'unitview-sig',
        disconnect=lambda sig_id: calls.append(('disconnect', sig_id)),
    )
    main_controller = SimpleNamespace(
        store_controller=store_controller,
        unit_controller=SimpleNamespace(view=unitview),
    )
    return main_controller, calls


def test_plugin_init_waits_for_targets_when_none_exist_yet():
    main_controller, calls = _plugin_main_controller(store=None, targets=[])

    plugin = Plugin('autocompletor', main_controller)

    assert isinstance(plugin.autocomp, AutoCompletor)
    assert ('store-loaded', plugin._on_store_loaded) in calls
    assert ('targets-created', plugin._connect_to_textboxes) in calls
    assert plugin._unitview_id == 'unitview-sig'


def test_plugin_init_connects_to_textboxes_when_targets_already_exist(monkeypatch):
    added = []
    monkeypatch.setattr(AutoCompletor, 'add_widget', lambda self, widget: added.append(widget))
    target = object()
    main_controller, calls = _plugin_main_controller(store=None, targets=[target])

    plugin = Plugin('autocompletor', main_controller)

    assert added == [target]
    assert plugin._unitview_id is None


def test_plugin_init_connects_to_an_already_loaded_store(monkeypatch):
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add', lambda f: None)
    store = SimpleNamespace(get_units=lambda: [])
    cursor = SimpleNamespace(connect=lambda *a: 'cursor-sig', deref=lambda: None)
    main_controller, calls = _plugin_main_controller(store=store, targets=[])
    main_controller.store_controller.cursor = cursor

    plugin = Plugin('autocompletor', main_controller)

    assert plugin.store_cursor is cursor


def test_plugin_destroy_disconnects_every_signal(monkeypatch):
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add', lambda f: None)
    main_controller, calls = _plugin_main_controller(store=None, targets=[])
    plugin = Plugin('autocompletor', main_controller)
    plugin._cursor_changed_id = 'cursor-sig'
    plugin.store_cursor = SimpleNamespace(disconnect=lambda sig: calls.append(('cursor-disconnect', sig)))

    plugin.destroy()

    assert plugin.autocomp._word_list == []
    assert ('disconnect', 'store-sig') in calls
    assert ('cursor-disconnect', 'cursor-sig') in calls
    assert ('disconnect', 'unitview-sig') in calls


def test_plugin_destroy_skips_optional_disconnects_when_never_set(monkeypatch):
    added = []
    monkeypatch.setattr(AutoCompletor, 'add_widget', lambda self, widget: added.append(widget))
    main_controller, calls = _plugin_main_controller(store=None, targets=[object()])
    plugin = Plugin('autocompletor', main_controller)

    plugin.destroy()  # must not raise despite no cursor_changed_id, and a None _unitview_id

    assert ('disconnect', 'store-sig') in calls


def test_on_cursor_change_first_call_just_remembers_the_unit(monkeypatch):
    scheduled = []
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add', scheduled.append)
    plugin = Plugin.__new__(Plugin)
    plugin.autocomp = AutoCompletor(main_controller=None, comp_len=1)
    first_unit = object()
    cursor = SimpleNamespace(deref=lambda: first_unit)

    plugin._on_cursor_change(cursor)
    scheduled[0]()

    assert plugin.lastunit is first_unit
    assert plugin.autocomp._word_list == []


def test_on_cursor_change_adds_the_previous_units_singular_target_words(monkeypatch):
    scheduled = []
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add', scheduled.append)
    plugin = Plugin.__new__(Plugin)
    plugin.autocomp = AutoCompletor(main_controller=None, comp_len=1)
    plugin.lastunit = SimpleNamespace(hasplural=lambda: False, target='helloworld')
    next_unit = object()
    cursor = SimpleNamespace(deref=lambda: next_unit)

    plugin._on_cursor_change(cursor)
    scheduled[0]()

    assert 'helloworld' in plugin.autocomp._word_list
    assert plugin.lastunit is next_unit


def test_on_cursor_change_skips_an_empty_singular_target(monkeypatch):
    scheduled = []
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add', scheduled.append)
    plugin = Plugin.__new__(Plugin)
    plugin.autocomp = AutoCompletor(main_controller=None, comp_len=1)
    plugin.lastunit = SimpleNamespace(hasplural=lambda: False, target='')
    cursor = SimpleNamespace(deref=lambda: object())

    plugin._on_cursor_change(cursor)
    scheduled[0]()  # must not raise

    assert plugin.autocomp._word_list == []


def test_on_cursor_change_adds_every_plural_forms_words_skipping_empty_ones(monkeypatch):
    scheduled = []
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add', scheduled.append)
    plugin = Plugin.__new__(Plugin)
    plugin.autocomp = AutoCompletor(main_controller=None, comp_len=1)
    plugin.lastunit = SimpleNamespace(
        hasplural=lambda: True,
        target=SimpleNamespace(strings=['', 'catscatscats']),
    )
    cursor = SimpleNamespace(deref=lambda: object())

    plugin._on_cursor_change(cursor)
    scheduled[0]()

    assert 'catscatscats' in plugin.autocomp._word_list


def test_on_store_loaded_adds_words_and_wires_the_cursor(monkeypatch):
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add', lambda f: None)
    plugin = Plugin.__new__(Plugin)
    plugin.autocomp = AutoCompletor(main_controller=None, comp_len=1)
    unit = SimpleNamespace(target='helloworld')
    store = SimpleNamespace(get_units=lambda: [unit])
    cursor_calls = []
    cursor = SimpleNamespace(
        connect=lambda signal, handler: cursor_calls.append((signal, handler)) or 'cursor-sig',
        deref=lambda: None,
    )
    storecontroller = SimpleNamespace(get_store=lambda: store, cursor=cursor)

    plugin._on_store_loaded(storecontroller)

    assert 'helloworld' in plugin.autocomp._word_list
    assert plugin.store_cursor is cursor
    assert cursor_calls == [('cursor-changed', plugin._on_cursor_change)]
    assert plugin._cursor_changed_id == 'cursor-sig'


def test_on_store_loaded_disconnects_a_previous_cursor_subscription(monkeypatch):
    monkeypatch.setattr('virtaal.plugins.autocompletor.GLib.idle_add', lambda f: None)
    plugin = Plugin.__new__(Plugin)
    plugin.autocomp = AutoCompletor(main_controller=None, comp_len=1)
    plugin._cursor_changed_id = 'old-sig'
    disconnected = []
    plugin.store_cursor = SimpleNamespace(disconnect=disconnected.append)
    store = SimpleNamespace(get_units=lambda: [])
    cursor = SimpleNamespace(connect=lambda *a: 'new-sig', deref=lambda: None)
    storecontroller = SimpleNamespace(get_store=lambda: store, cursor=cursor)

    plugin._on_store_loaded(storecontroller)

    assert disconnected == ['old-sig']
    assert plugin._cursor_changed_id == 'new-sig'
