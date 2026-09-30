#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Tests for AutoCorrector's load_dictionary()/_read_document_list()
and autocorrect() - the plain data logic, no real GTK widgets
involved. Fixture content is the same real, live-fetched af-ZA
DocumentList.xml excerpt test_autocorrect_source.py already uses."""

import os
from types import SimpleNamespace

import pytest
from gi.repository import Gtk

from virtaal.common import pan_app
from virtaal.plugins.autocorrector import AutoCorrector, Plugin
from virtaal.support.asset_manifest import entry_shas, installed_asset_key
from virtaal.support.test_autocorrect_source import AF_ZA_DOCUMENT_LIST
from virtaal.views.widgets.textbox import TextBox


def _write_document_list(acorpath, lang, content=AF_ZA_DOCUMENT_LIST):
    lang_dir = acorpath / lang
    lang_dir.mkdir(parents=True, exist_ok=True)
    (lang_dir / 'DocumentList.xml').write_bytes(content)


def test_load_dictionary_with_nothing_local_is_empty(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    assert corrector.correctiondict == {}
    assert corrector.lang == ''


def test_load_dictionary_reads_the_exact_locale_directory(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector.load_dictionary('af_ZA')

    assert corrector.lang == 'af_ZA'
    assert 'adt' in corrector.correctiondict
    assert corrector.correctiondict['adt'][0] == 'dat'


def test_load_dictionary_skips_leading_comments(tmp_path):
    # "ca"'s real DocumentList.xml (and others) have license-header XML
    # comments as top-level children, alongside the real block entries.
    content = b"""<?xml version="1.0" encoding="utf-8"?>
<block-list:block-list xmlns:block-list="http://openoffice.org/2001/block-list">
<!-- license header -->
  <block-list:block block-list:abbreviated-name="adt" block-list:name="dat"/>
</block-list:block-list>
"""
    _write_document_list(tmp_path, 'af_ZA', content=content)
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector.load_dictionary('af_ZA')  # must not raise

    assert corrector.correctiondict['adt'][0] == 'dat'


def test_load_dictionary_accepts_hyphenated_input(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector.load_dictionary('af-ZA')

    assert corrector.lang == 'af_ZA'
    assert 'basseer' in corrector.correctiondict


def test_load_dictionary_falls_back_to_bare_language_directory(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector.load_dictionary('af')

    assert corrector.lang == 'af'
    assert 'adt' in corrector.correctiondict


def test_load_dictionary_short_circuits_on_the_same_language(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')
    corrector.correctiondict['sentinel'] = 'still here'

    corrector.load_dictionary('af_ZA')  # same lang, no force -> no-op

    assert 'sentinel' in corrector.correctiondict


def test_load_dictionary_force_reloads_the_same_language(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    assert corrector.correctiondict == {}

    # Simulate a download landing after the first (empty) attempt.
    _write_document_list(tmp_path, 'af_ZA')
    corrector.load_dictionary('af_ZA', force=True)

    assert 'adt' in corrector.correctiondict


def test_autocorrect_replaces_a_known_abbreviation(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')

    reprange, replacement = corrector.autocorrect('Ek adt', 6)

    assert replacement == 'dat'
    assert reprange == (3, 6)


def test_autocorrect_with_no_dictionary_does_nothing(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    reprange, replacement = corrector.autocorrect('Ek adt', 6)

    assert reprange is None
    assert replacement == ''


def test_autocorrect_with_a_dictionary_but_no_match_does_nothing(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')

    reprange, replacement = corrector.autocorrect('nothing correctable here', 24)

    assert reprange is None
    assert replacement == ''


def test_add_widget_does_nothing_without_a_dictionary(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector.add_widget(object())  # must not raise, silently ignored

    assert corrector.widgets == set()


def test_add_widget_ignores_a_widget_already_added(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')
    already_added = object()
    corrector.widgets.add(already_added)

    corrector.add_widget(already_added)  # must not raise or duplicate

    assert corrector.widgets == {already_added}


def test_add_widget_rejects_an_unsupported_widget_type(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')

    try:
        corrector.add_widget(object())
        assert False, 'expected ValueError'
    except ValueError:
        pass


def test_remove_widget_does_nothing_without_a_dictionary(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector.remove_widget(object())  # must not raise


def test_init_falls_back_to_curdir_for_a_missing_acorpath():
    corrector = AutoCorrector(main_controller=None, acorpath='/no/such/path/at/all')

    assert corrector.acorpath == os.path.curdir


def test_read_document_list_returns_none_when_acorpath_is_not_a_directory(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.acorpath = str(tmp_path / 'does-not-exist')

    assert corrector._read_document_list('af_ZA') is None


def test_read_document_list_returns_none_when_nothing_matches(tmp_path):
    (tmp_path / 'xx').mkdir()
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    assert corrector._read_document_list('af_ZA') is None


def test_load_dictionary_with_a_lang_but_nothing_local_is_empty(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector.load_dictionary('xx_YY')

    assert corrector.correctiondict == {}
    assert corrector.lang == ''


# widget registration - _add_textbox()/_remove_textbox()/clear_widgets()/
# set_widgets(), and remove_widget()'s real dispatch branch #

def _fake_widget():
    """A TextBox type tag (for isinstance checks) with its connect()/
        disconnect() overridden - avoids constructing a real,
        GTK-widget-backed TextBox."""
    calls = []
    widget = TextBox.__new__(TextBox)
    widget.connect = lambda signal, handler: calls.append(('connect', signal)) or 'sigid'
    widget.disconnect = lambda sig_id: calls.append(('disconnect', sig_id))
    return widget, calls


def test_add_textbox_connects_and_registers_the_widget(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')
    widget, calls = _fake_widget()

    corrector._add_textbox(widget)

    assert calls == [('connect', 'text-inserted')]
    assert corrector._textbox_handler_ids[widget] == 'sigid'
    assert widget in corrector.widgets


def test_remove_widget_disconnects_a_registered_textbox(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')
    widget, calls = _fake_widget()
    corrector._add_textbox(widget)

    corrector.remove_widget(widget)

    assert ('disconnect', 'sigid') in calls
    assert widget not in corrector.widgets


def test_remove_textbox_does_nothing_before_any_widget_was_ever_added(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector._remove_textbox(object())  # must not raise


def test_clear_widgets_removes_every_registered_widget(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')
    w1, _ = _fake_widget()
    w2, _ = _fake_widget()
    corrector._add_textbox(w1)
    corrector._add_textbox(w2)

    corrector.clear_widgets()

    assert corrector.widgets == set()


def test_set_widgets_replaces_the_current_set(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')
    old, _ = _fake_widget()
    corrector._add_textbox(old)
    new, _ = _fake_widget()

    corrector.set_widgets([new])

    assert corrector.widgets == {new}


# _on_insert_text() - the actual autocorrect-while-typing logic #

class _FakeElem:
    """A stand-in for the StringElem passed to _on_insert_text() - its
        gui_info bridges GUI text-buffer offsets and "tree" (logical
        string) offsets. treeindex_to_iter() is routed through a real
        Gtk.TextBuffer so the deferred correction can really run."""
    def __init__(self, text, gui_to_tree_index, tree_to_gui_index, buf):
        self._text = text
        self._gui_to_tree = gui_to_tree_index
        self._tree_to_gui = tree_to_gui_index
        self.gui_info = SimpleNamespace(
            gui_to_tree_index=lambda cursorpos: self._gui_to_tree,
            tree_to_gui_index=lambda tree_index: self._tree_to_gui,
            treeindex_to_iter=lambda index, start_at=None: buf.get_iter_at_offset(index),
        )

    def __str__(self):
        return self._text


def test_on_insert_text_ignores_a_non_string_insertion(tmp_path):
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))

    corrector._on_insert_text(SimpleNamespace(), text=object(), cursorpos=0, elem=None)  # must not raise


def test_on_insert_text_ignores_a_mid_word_insertion(tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')

    corrector._on_insert_text(SimpleNamespace(), text='d', cursorpos=0, elem=None)  # not a word boundary


def test_on_insert_text_does_nothing_without_a_match(monkeypatch, tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')
    monkeypatch.setattr('virtaal.plugins.autocorrector.GLib.idle_add',
                         lambda *a, **k: pytest.fail('must not correct without a match'))
    buf = Gtk.TextBuffer()
    buf.set_text('nothing correctable ')
    elem = _FakeElem('nothing correctable', gui_to_tree_index=20, tree_to_gui_index=0, buf=buf)

    corrector._on_insert_text(SimpleNamespace(), text=' ', cursorpos=99, elem=elem)


def test_on_insert_text_schedules_and_applies_a_correction(monkeypatch, tmp_path):
    _write_document_list(tmp_path, 'af_ZA')
    corrector = AutoCorrector(main_controller=None, acorpath=str(tmp_path))
    corrector.load_dictionary('af_ZA')
    undo_calls = []
    corrector.main_controller = SimpleNamespace(undo_controller=SimpleNamespace(
        record_start=lambda: undo_calls.append('start'),
        record_stop=lambda: undo_calls.append('stop'),
    ))
    scheduled = []
    monkeypatch.setattr('virtaal.plugins.autocorrector.GLib.idle_add', scheduled.append)
    buf = Gtk.TextBuffer()
    buf.set_text('Ek adt ')
    elem = _FakeElem('Ek adt', gui_to_tree_index=6, tree_to_gui_index=3, buf=buf)
    refresh_calls = []
    textbox = SimpleNamespace(buffer=buf, refresh=lambda: refresh_calls.append('refreshed'))

    corrector._on_insert_text(textbox, text=' ', cursorpos=99, elem=elem)

    assert len(scheduled) == 1
    assert scheduled[0]() is False  # runs correct_text() for real

    assert buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True) == 'Ek dat '
    assert undo_calls == ['start', 'stop']
    assert len(scheduled) == 2  # correct_text() itself scheduled a follow-up refresh()

    scheduled[1]()  # run refresh() for real
    assert textbox.refresh_cursor_pos == 3 + len('dat') + len(' ')
    assert refresh_calls == ['refreshed']


# Plugin - completely untested until now #

class _FakeAutocorrectDownloader:
    started = []  # live-discovery start() calls: [lang, ...]
    known_files_started = []  # start_with_known_files() calls: [(lang, folder, files), ...]
    instances = []

    def __init__(self, lang, on_done):
        self.lang = lang
        self.on_done = on_done
        _FakeAutocorrectDownloader.instances.append(self)

    def start(self):
        _FakeAutocorrectDownloader.started.append(self.lang)

    def start_with_known_files(self, folder, files):
        _FakeAutocorrectDownloader.known_files_started.append((self.lang, folder, files))


class _FakeAssetManifest:
    """entries: {locale: entry}. has_data defaults to whether entries
    is non-empty - pass it explicitly for the "manifest was genuinely
    fetched but has nothing for this locale" case, distinct from
    "never fetched at all". ensure_fresh() always calls on_done()
    immediately - the manifest's own refresh timing is tested in
    test_asset_manifest.py, not here."""

    def __init__(self, entries=None, has_data=None):
        self.entries = entries or {}
        self._has_data = bool(self.entries) if has_data is None else has_data

    def ensure_fresh(self, on_done=None):
        (on_done or (lambda: None))()

    def get(self, resource_type, locale_code):
        assert resource_type == 'autocorrect'
        return self.entries.get(locale_code)

    def has_data(self):
        return self._has_data


def _fake_cursor():
    calls = []
    cursor = SimpleNamespace(
        connect=lambda signal, handler: calls.append((signal, handler)) or 'cursor-sig',
        disconnect=lambda sig_id: calls.append(('disconnect', sig_id)),
    )
    return cursor, calls


def _plugin_main_controller(store=None, targets=None, target_lang_code='af'):
    calls = []
    store_controller = SimpleNamespace(
        connect=lambda signal, handler: calls.append((signal, handler)) or 'store-sig',
        disconnect=lambda sig_id: calls.append(('disconnect', sig_id)),
        get_store=lambda: store,
    )
    lang_controller = SimpleNamespace(
        connect=lambda signal, handler: calls.append((signal, handler)) or 'lang-sig',
        target_lang=SimpleNamespace(code=target_lang_code),
    )
    unitview = SimpleNamespace(targets=targets or [])
    main_controller = SimpleNamespace(
        store_controller=store_controller,
        lang_controller=lang_controller,
        unit_controller=SimpleNamespace(view=unitview),
    )
    return main_controller, calls


def _init_plugin(monkeypatch, acorpath, manifest_entries=None, manifest_has_data=None, lull_calls=None, **kwargs):
    monkeypatch.setattr('virtaal.support.autocorrect_source.autocorrect_root_dir', lambda: str(acorpath))
    monkeypatch.setattr('virtaal.plugins.autocorrector.GLib.idle_add', lambda f: f())
    monkeypatch.setattr('virtaal.support.autocorrect_downloader.AutocorrectDownloader', _FakeAutocorrectDownloader)
    _FakeAutocorrectDownloader.started = []
    _FakeAutocorrectDownloader.known_files_started = []
    _FakeAutocorrectDownloader.instances = []
    lull_calls = lull_calls if lull_calls is not None else []
    main_controller, calls = _plugin_main_controller(**kwargs)
    plugin = Plugin(
        'autocorrector', main_controller,
        asset_manifest=_FakeAssetManifest(manifest_entries, has_data=manifest_has_data),
        schedule_after_idle_lull=lambda callback: lull_calls.append(callback))
    return plugin, main_controller, calls


def test_plugin_init_wires_store_and_lang_signals(monkeypatch, tmp_path):
    plugin, main_controller, calls = _init_plugin(monkeypatch, tmp_path, store=None, targets=[])

    assert isinstance(plugin.autocorr, AutoCorrector)
    assert any(signal == 'store-loaded' for signal, _ in calls)
    assert any(signal == 'target-lang-changed' for signal, _ in calls)


def test_on_store_loaded_wires_dictionary_and_cursor(monkeypatch, tmp_path):
    _write_document_list(tmp_path, 'af')
    plugin, main_controller, calls = _init_plugin(monkeypatch, tmp_path, store=None, targets=[], target_lang_code='af')
    on_store_loaded = next(h for s, h in calls if s == 'store-loaded')
    cursor, cursor_calls = _fake_cursor()
    storecontroller = SimpleNamespace(cursor=cursor)

    on_store_loaded(storecontroller)

    assert plugin.autocorr.lang == 'af'
    assert 'adt' in plugin.autocorr.correctiondict
    assert plugin.store_cursor is cursor
    assert cursor_calls[0][0] == 'cursor-changed'
    assert plugin._cursor_changed_id == 'cursor-sig'


def test_on_store_loaded_disconnects_a_previous_cursor_subscription(monkeypatch, tmp_path):
    _write_document_list(tmp_path, 'af')
    plugin, main_controller, calls = _init_plugin(monkeypatch, tmp_path, store=None, targets=[], target_lang_code='af')
    on_store_loaded = next(h for s, h in calls if s == 'store-loaded')
    first_cursor, first_calls = _fake_cursor()
    on_store_loaded(SimpleNamespace(cursor=first_cursor))

    second_cursor, second_calls = _fake_cursor()
    on_store_loaded(SimpleNamespace(cursor=second_cursor))

    assert ('disconnect', 'cursor-sig') in first_calls
    assert plugin.store_cursor is second_cursor


def test_on_store_loaded_downloads_when_nothing_local_covers_the_language(monkeypatch, tmp_path):
    plugin, main_controller, calls = _init_plugin(monkeypatch, tmp_path, store=None, targets=[], target_lang_code='xx')
    on_store_loaded = next(h for s, h in calls if s == 'store-loaded')
    cursor, _ = _fake_cursor()

    on_store_loaded(SimpleNamespace(cursor=cursor))

    assert plugin.autocorr.correctiondict == {}
    assert _FakeAutocorrectDownloader.started == ['xx']


def test_maybe_download_reloads_and_reattaches_when_the_download_completes(monkeypatch, tmp_path):
    def fake_start(self):
        _FakeAutocorrectDownloader.started.append(self.lang)
        _write_document_list(tmp_path, self.lang)  # simulate the download landing
        self.on_done(True)
    monkeypatch.setattr(_FakeAutocorrectDownloader, 'start', fake_start)
    plugin, main_controller, calls = _init_plugin(monkeypatch, tmp_path, store=None, targets=[], target_lang_code='xx')
    on_store_loaded = next(h for s, h in calls if s == 'store-loaded')
    cursor, _ = _fake_cursor()

    on_store_loaded(SimpleNamespace(cursor=cursor))

    assert plugin.autocorr.lang == 'xx'
    assert 'adt' in plugin.autocorr.correctiondict


def test_maybe_download_only_tries_once_per_language_per_run(monkeypatch, tmp_path):
    plugin, main_controller, calls = _init_plugin(monkeypatch, tmp_path, store=None, targets=[], target_lang_code='xx')
    on_store_loaded = next(h for s, h in calls if s == 'store-loaded')
    cursor, _ = _fake_cursor()

    on_store_loaded(SimpleNamespace(cursor=cursor))
    on_store_loaded(SimpleNamespace(cursor=cursor))

    assert _FakeAutocorrectDownloader.started == ['xx']


def test_does_nothing_when_a_fetched_manifest_confirms_no_entry_for_locale(monkeypatch, tmp_path):
    # The manifest is comprehensive once fetched - a miss here is
    # authoritative, not "we don't know yet" - must not redo live
    # discovery every cold start for a locale with genuinely nothing.
    plugin, main_controller, calls = _init_plugin(
        monkeypatch, tmp_path, store=None, targets=[], target_lang_code='xx', manifest_has_data=True)
    on_store_loaded = next(h for s, h in calls if s == 'store-loaded')
    cursor, _ = _fake_cursor()

    on_store_loaded(SimpleNamespace(cursor=cursor))

    assert _FakeAutocorrectDownloader.started == []
    assert _FakeAutocorrectDownloader.known_files_started == []


_XX_ENTRY = {'folder': 'xx', 'files': [{'name': 'DocumentList.xml', 'sha': 's1'}]}


def test_downloads_via_known_files_after_a_lull_when_manifest_has_an_entry(monkeypatch, tmp_path):
    pan_app.settings.installed_assets = {}
    lull_calls = []
    plugin, main_controller, calls = _init_plugin(
        monkeypatch, tmp_path, store=None, targets=[], target_lang_code='xx',
        manifest_entries={'xx': _XX_ENTRY}, lull_calls=lull_calls)
    on_store_loaded = next(h for s, h in calls if s == 'store-loaded')
    cursor, _ = _fake_cursor()

    on_store_loaded(SimpleNamespace(cursor=cursor))

    assert _FakeAutocorrectDownloader.known_files_started == []  # not yet - waiting for the lull
    assert len(lull_calls) == 1
    lull_calls[0]()  # simulate the lull passing

    assert _FakeAutocorrectDownloader.known_files_started == [('xx', 'xx', ['DocumentList.xml'])]
    assert _FakeAutocorrectDownloader.started == []


def test_skips_download_when_installed_sha_already_matches_the_manifest(monkeypatch, tmp_path):
    pan_app.settings.installed_assets = {installed_asset_key('autocorrect', 'xx'): entry_shas(_XX_ENTRY)}
    plugin, main_controller, calls = _init_plugin(
        monkeypatch, tmp_path, store=None, targets=[], target_lang_code='xx',
        manifest_entries={'xx': _XX_ENTRY})
    on_store_loaded = next(h for s, h in calls if s == 'store-loaded')
    cursor, _ = _fake_cursor()

    on_store_loaded(SimpleNamespace(cursor=cursor))

    assert _FakeAutocorrectDownloader.started == []
    assert _FakeAutocorrectDownloader.known_files_started == []


def test_records_installed_sha_only_on_a_successful_known_download(monkeypatch, tmp_path):
    pan_app.settings.installed_assets = {}
    lull_calls = []
    plugin, main_controller, calls = _init_plugin(
        monkeypatch, tmp_path, store=None, targets=[], target_lang_code='xx',
        manifest_entries={'xx': _XX_ENTRY}, lull_calls=lull_calls)
    on_store_loaded = next(h for s, h in calls if s == 'store-loaded')
    cursor, _ = _fake_cursor()
    on_store_loaded(SimpleNamespace(cursor=cursor))
    lull_calls[0]()
    key = installed_asset_key('autocorrect', 'xx')
    downloader = _FakeAutocorrectDownloader.instances[0]

    downloader.on_done(False)
    assert key not in pan_app.settings.installed_assets

    downloader.on_done(True)
    assert pan_app.settings.installed_assets[key] == entry_shas(_XX_ENTRY)


def test_plugin_connects_to_an_already_loaded_store_at_construction(monkeypatch, tmp_path):
    _write_document_list(tmp_path, 'af')
    cursor, _ = _fake_cursor()
    store = SimpleNamespace(get_units=lambda: [])
    main_controller, calls = _plugin_main_controller(store=store, targets=[], target_lang_code='af')
    main_controller.store_controller.cursor = cursor
    monkeypatch.setattr('virtaal.support.autocorrect_source.autocorrect_root_dir', lambda: str(tmp_path))
    monkeypatch.setattr('virtaal.plugins.autocorrector.GLib.idle_add', lambda f: f())

    plugin = Plugin('autocorrector', main_controller)

    assert plugin.store_cursor is cursor
    assert plugin.autocorr.lang == 'af'


def test_on_target_lang_changed_reloads_the_dictionary_and_reattaches_widgets(monkeypatch, tmp_path):
    _write_document_list(tmp_path, 'af')
    widget, widget_calls = _fake_widget()
    plugin, main_controller, calls = _init_plugin(
        monkeypatch, tmp_path, store=None, targets=[widget], target_lang_code='en')
    on_target_lang_changed = next(h for s, h in calls if s == 'target-lang-changed')

    on_target_lang_changed(main_controller.lang_controller, 'af')

    assert plugin.autocorr.lang == 'af'
    assert ('connect', 'text-inserted') in widget_calls
    assert widget in plugin.autocorr.widgets


def test_plugin_destroy_disconnects_every_signal(monkeypatch, tmp_path):
    plugin, main_controller, calls = _init_plugin(monkeypatch, tmp_path, store=None, targets=[], target_lang_code='af')
    plugin._cursor_changed_id = 'cursor-sig'
    plugin.store_cursor = SimpleNamespace(disconnect=lambda sig: calls.append(('cursor-disconnect', sig)))

    plugin.destroy()

    assert ('disconnect', 'store-sig') in calls
    assert ('cursor-disconnect', 'cursor-sig') in calls


def test_plugin_destroy_skips_the_optional_cursor_disconnect_when_never_set(monkeypatch, tmp_path):
    plugin, main_controller, calls = _init_plugin(monkeypatch, tmp_path, store=None, targets=[], target_lang_code='af')

    plugin.destroy()  # must not raise despite no _cursor_changed_id ever set

    assert ('disconnect', 'store-sig') in calls
