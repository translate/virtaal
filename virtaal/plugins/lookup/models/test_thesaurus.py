#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from urllib.error import HTTPError

from gi.repository import Gtk

from virtaal.plugins.lookup.models import thesaurus as thesaurus_module
from virtaal.plugins.lookup.models.thesaurus import LookupModel
from virtaal.support import mythes

SAMPLE_DAT = (
    'UTF-8\n'
    'abaja|1\n'
    '-|abaja|sukmana|płaszcz\n'
).encode()


class _FakeUndoController:
    def __init__(self):
        self.calls = []

    def record_start(self):
        self.calls.append('start')

    def record_stop(self):
        self.calls.append('stop')


class _FakeLanguage:
    def __init__(self, code):
        self.code = code


class _FakeLangController:
    """Real signal dispatch (not a mock) - source/target-lang-changed
    also fires on opening a file, not just an explicit language-picker
    change, and the plugin's whole point is reacting to either."""

    def __init__(self, source_lang=None, target_lang=None):
        self.source_lang = _FakeLanguage(source_lang) if source_lang else None
        self.target_lang = _FakeLanguage(target_lang) if target_lang else None
        self._handlers = {}

    def connect(self, signal, handler):
        self._handlers.setdefault(signal, []).append(handler)

    def emit(self, signal, code):
        for handler in self._handlers.get(signal, []):
            handler(self, code)


class _FakeMainController:
    def __init__(self, source_lang=None, target_lang=None):
        self.undo_controller = _FakeUndoController()
        self.lang_controller = _FakeLangController(source_lang, target_lang)


class _FakeController:
    def __init__(self, source_lang=None, target_lang=None):
        self.main_controller = _FakeMainController(source_lang, target_lang)


class _FakeThread:
    def __init__(self, target=None, args=(), daemon=None):
        self.target = target
        self.args = args
        self.started = False

    def start(self):
        self.started = True


def _make_model(source_lang=None, target_lang=None):
    return LookupModel('thesaurus', _FakeController(source_lang, target_lang))


def _write_dat(cache_dir, locale_code, content):
    folder = cache_dir / locale_code
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'th_sample.dat').write_bytes(content)


def _patch_threads(monkeypatch):
    threads = []
    monkeypatch.setattr(thesaurus_module.threading, 'Thread', lambda **kwargs: threads.append(_FakeThread(**kwargs)) or threads[-1])
    return threads


def test_create_menu_items_offers_a_download_when_nothing_is_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    model = _make_model()

    items = model.create_menu_items('abaja', 'source', 'pl_PL', 'en', None)

    assert len(items) == 1
    assert 'Download' in items[0].get_label()


def test_create_menu_items_starts_a_background_parse_when_a_dat_is_cached_but_not_yet_parsed(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    _write_dat(tmp_path, 'pl_PL', SAMPLE_DAT)
    threads = _patch_threads(monkeypatch)
    model = _make_model()

    items = model.create_menu_items('abaja', 'source', 'pl_PL', 'en', None)

    assert len(items) == 1
    assert 'Loading' in items[0].get_label()
    assert not items[0].get_sensitive()
    assert len(threads) == 1
    assert threads[0].started
    assert threads[0].target == model._parse
    assert 'pl_PL' in model._parsing


def test_create_menu_items_shows_loading_without_starting_a_second_parse(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    _write_dat(tmp_path, 'pl_PL', SAMPLE_DAT)
    threads = _patch_threads(monkeypatch)
    model = _make_model()
    model._parsing.add('pl_PL')

    items = model.create_menu_items('abaja', 'source', 'pl_PL', 'en', None)

    assert len(items) == 1
    assert 'Loading' in items[0].get_label()
    assert threads == []


def test_on_parsed_caches_the_result_and_clears_the_parsing_flag():
    model = _make_model()
    model._parsing.add('pl_PL')
    thesaurus = mythes.parse_thesaurus(SAMPLE_DAT)

    model._on_parsed('pl_PL', thesaurus)

    assert model._thesauruses['pl_PL'] is thesaurus
    assert 'pl_PL' not in model._parsing


def test_on_parse_failed_stops_retrying_the_same_cached_dat():
    model = _make_model()
    model._parsing.add('pl_PL')

    model._on_parse_failed('pl_PL')

    assert 'pl_PL' not in model._parsing
    assert 'pl_PL' in model._parse_failed


def test_create_menu_items_does_not_reparse_a_locale_that_already_failed(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    _write_dat(tmp_path, 'pl_PL', SAMPLE_DAT)
    threads = _patch_threads(monkeypatch)
    model = _make_model()
    model._parse_failed.add('pl_PL')

    items = model.create_menu_items('abaja', 'source', 'pl_PL', 'en', None)

    assert threads == []
    assert len(items) == 1
    assert 'Download' in items[0].get_label()


def test_start_check_clears_a_previous_parse_failure(monkeypatch):
    threads = _patch_threads(monkeypatch)
    model = _make_model()
    model._parse_failed.add('pl_PL')

    model._start_check('pl_PL')

    assert 'pl_PL' not in model._parse_failed
    assert len(threads) == 1


def test_create_menu_items_offers_synonyms_once_a_thesaurus_is_parsed():
    model = _make_model()
    model._thesauruses['pl_PL'] = mythes.parse_thesaurus(SAMPLE_DAT)

    items = model.create_menu_items('abaja', 'source', 'pl_PL', 'en', None)

    assert len(items) == 1
    labels = [i.get_label() for i in items[0].get_submenu().get_children()]
    assert labels == ['abaja', 'sukmana', 'płaszcz']


def test_create_menu_items_returns_nothing_for_an_unknown_word():
    model = _make_model()
    model._thesauruses['pl_PL'] = mythes.parse_thesaurus(SAMPLE_DAT)

    assert model.create_menu_items('notaword', 'source', 'pl_PL', 'en', None) == []


def test_create_menu_items_returns_nothing_for_an_empty_selection(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    model = _make_model()

    assert model.create_menu_items('   ', 'source', 'pl_PL', 'en', None) == []


def test_create_menu_items_uses_the_target_language_for_a_target_selection():
    model = _make_model()
    model._thesauruses['en'] = mythes.parse_thesaurus(SAMPLE_DAT)

    items = model.create_menu_items('abaja', 'target', 'pl_PL', 'en', None)

    assert len(items) == 1
    assert items[0].get_label() == 'Synonyms'


class _Textbox:
    def __init__(self, buffer, role='target'):
        self.buffer = buffer
        self.role = role


def test_replace_selection_swaps_the_selected_text_and_records_undo():
    buf = Gtk.TextBuffer()
    buf.set_text('a płaszcz b')
    start = buf.get_iter_at_offset(2)
    end = buf.get_iter_at_offset(9)
    buf.select_range(start, end)
    textbox = _Textbox(buf)

    model = _make_model()
    model._replace_selection(textbox, 'sukmana')

    assert buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False) == 'a sukmana b'
    assert model.controller.main_controller.undo_controller.calls == ['start', 'stop']


def test_replace_selection_leaves_source_text_untouched():
    buf = Gtk.TextBuffer()
    buf.set_text('a płaszcz b')
    start = buf.get_iter_at_offset(2)
    end = buf.get_iter_at_offset(9)
    buf.select_range(start, end)
    textbox = _Textbox(buf, role='source')

    model = _make_model()
    model._replace_selection(textbox, 'sukmana')

    assert buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False) == 'a płaszcz b'
    assert model.controller.main_controller.undo_controller.calls == []


def test_download_writes_only_dat_files_ignoring_a_missing_idx(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    fetched = []

    def fake_fetch(folder, filename):
        fetched.append(filename)
        if filename.endswith('.idx'):
            raise HTTPError('url', 404, 'not found', {}, None)
        return b'UTF-8\nabaja|1\n-|abaja\n'
    monkeypatch.setattr(thesaurus_module, 'fetch_dictionary_file', fake_fetch)

    model = _make_model()
    model._download('fr_FR', 'fr_FR', ['thes_fr.dat', 'thes_fr.idx'])

    assert fetched == ['thes_fr.dat']
    assert (tmp_path / 'fr_FR' / 'thes_fr.dat').read_bytes() == b'UTF-8\nabaja|1\n-|abaja\n'
    assert 'fr_FR' not in model._downloading


def test_on_download_does_not_start_a_second_thread_while_one_is_in_flight(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    threads = _patch_threads(monkeypatch)
    model = _make_model()

    model._on_download(None, 'pl_PL')
    model._on_download(None, 'pl_PL')

    assert len(threads) == 1
    assert threads[0].started


def test_on_download_finished_starts_parsing_the_dat_it_just_fetched(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    _write_dat(tmp_path, 'pl_PL', SAMPLE_DAT)
    threads = _patch_threads(monkeypatch)
    model = _make_model()

    model._on_download_finished('pl_PL', True)

    assert len(threads) == 1
    assert threads[0].target == model._parse
    assert threads[0].args == ('pl_PL', str(tmp_path / 'pl_PL' / 'th_sample.dat'))


def test_on_download_finished_does_not_parse_after_a_failed_download(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    threads = _patch_threads(monkeypatch)
    model = _make_model()

    model._on_download_finished('pl_PL', False)

    assert threads == []


def test_init_auto_downloads_for_the_current_source_and_target_languages(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    threads = _patch_threads(monkeypatch)

    model = _make_model(source_lang='pl_PL', target_lang='en')

    assert len(threads) == 2
    assert {t.args[0] for t in threads} == {'pl_PL', 'en'}
    assert all(t.started for t in threads)


def test_init_parses_instead_of_downloading_when_already_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    _write_dat(tmp_path, 'pl_PL', SAMPLE_DAT)
    threads = _patch_threads(monkeypatch)

    model = _make_model(source_lang='pl_PL', target_lang='en')

    assert len(threads) == 2
    check_threads = [t for t in threads if t.target == model._check]
    parse_threads = [t for t in threads if t.target == model._parse]
    assert [t.args[0] for t in check_threads] == ['en']
    assert [t.args[0] for t in parse_threads] == ['pl_PL']


def test_lang_changed_signal_triggers_an_auto_download(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    threads = _patch_threads(monkeypatch)
    model = _make_model()
    assert threads == []

    model.controller.main_controller.lang_controller.emit('target-lang-changed', 'de_DE')

    assert len(threads) == 1
    assert threads[0].args[0] == 'de_DE'


def test_maybe_auto_download_does_not_retry_the_same_locale_twice(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    threads = _patch_threads(monkeypatch)
    model = _make_model()

    model._maybe_auto_download('de_DE')
    model._maybe_auto_download('de_DE')

    assert len(threads) == 1


def test_maybe_auto_download_normalises_hyphenated_locale_codes(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    threads = _patch_threads(monkeypatch)
    model = _make_model()

    model._maybe_auto_download('de-DE')

    assert len(threads) == 1
    assert threads[0].args[0] == 'de_DE'


# Checking availability before ever downloading (a light tree + xcu
# fetch, not the .dat file itself) - a locale confirmed to have no
# thesaurus in the repo at all should never offer a "Download" button
# that would only ever fail.

def _patch_idle_add_to_run_immediately(monkeypatch):
    monkeypatch.setattr(thesaurus_module.GLib, 'idle_add', lambda func, *args: func(*args))


def test_check_marks_a_locale_unavailable_when_nothing_is_found(monkeypatch):
    monkeypatch.setattr(thesaurus_module, 'fetch_dictionary_tree', lambda: {})
    monkeypatch.setattr(thesaurus_module, 'list_dictionary_folders', lambda tree: {})
    monkeypatch.setattr(thesaurus_module, 'find_dictionary', lambda *a, **k: None)
    _patch_idle_add_to_run_immediately(monkeypatch)
    model = _make_model()
    model._checking.add('af_ZA')

    model._check('af_ZA')

    assert 'af_ZA' not in model._checking
    assert 'af_ZA' in model._unavailable


def test_check_starts_a_download_when_a_thesaurus_is_found(monkeypatch):
    monkeypatch.setattr(thesaurus_module, 'fetch_dictionary_tree', lambda: {})
    monkeypatch.setattr(thesaurus_module, 'list_dictionary_folders', lambda tree: {})
    monkeypatch.setattr(thesaurus_module, 'find_dictionary', lambda *a, **k: ('pl', ['th_pl_PL.dat']))
    _patch_idle_add_to_run_immediately(monkeypatch)
    threads = _patch_threads(monkeypatch)
    model = _make_model()
    model._checking.add('pl_PL')

    model._check('pl_PL')

    assert 'pl_PL' not in model._checking
    assert 'pl_PL' in model._downloading
    assert len(threads) == 1
    assert threads[0].target == model._download
    assert threads[0].args[0] == 'pl_PL'


def test_create_menu_items_returns_nothing_for_an_unavailable_locale():
    model = _make_model()
    model._unavailable.add('af_ZA')

    assert model.create_menu_items('word', 'source', 'af_ZA', 'en', None) == []


def test_create_menu_items_shows_a_checking_status():
    model = _make_model()
    model._checking.add('pl_PL')

    items = model.create_menu_items('word', 'source', 'pl_PL', 'en', None)

    assert len(items) == 1
    assert 'Checking' in items[0].get_label()
    assert not items[0].get_sensitive()


def test_create_menu_items_shows_the_language_name_while_downloading():
    model = _make_model()
    model._downloading.add('pl_PL')

    items = model.create_menu_items('word', 'source', 'pl_PL', 'en', None)

    assert len(items) == 1
    assert items[0].get_label() == 'Downloading Polish thesaurus…'
    assert not items[0].get_sensitive()


def test_create_menu_items_download_button_names_the_language():
    model = _make_model()

    items = model.create_menu_items('word', 'source', 'af_ZA', 'en', None)

    assert len(items) == 1
    assert items[0].get_label() == 'Download Afrikaans thesaurus…'
    assert items[0].get_sensitive()


def test_on_download_starts_a_check_not_a_direct_download(monkeypatch):
    threads = _patch_threads(monkeypatch)
    model = _make_model()

    model._on_download(None, 'pl_PL')

    assert 'pl_PL' in model._checking
    assert threads[0].target == model._check
