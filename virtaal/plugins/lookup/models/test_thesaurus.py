#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

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


class _FakeMainController:
    def __init__(self):
        self.undo_controller = _FakeUndoController()


class _FakeController:
    def __init__(self):
        self.main_controller = _FakeMainController()


def _make_model():
    return LookupModel('thesaurus', _FakeController())


def _write_dat(cache_dir, locale_code, content):
    folder = cache_dir / locale_code
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'th_sample.dat').write_bytes(content)


class _FakeThread:
    def __init__(self, target=None, args=(), daemon=None):
        self.target = target
        self.args = args
        self.started = False

    def start(self):
        self.started = True


def test_create_menu_items_offers_a_download_when_nothing_is_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    model = _make_model()

    items = model.create_menu_items('abaja', 'source', 'pl_PL', 'en', None)

    assert len(items) == 1
    assert 'Download' in items[0].get_label()


def test_create_menu_items_starts_a_background_parse_when_a_dat_is_cached_but_not_yet_parsed(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    _write_dat(tmp_path, 'pl_PL', SAMPLE_DAT)
    threads = []
    monkeypatch.setattr(thesaurus_module.threading, 'Thread', lambda **kwargs: threads.append(_FakeThread(**kwargs)) or threads[-1])
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
    threads = []
    monkeypatch.setattr(thesaurus_module.threading, 'Thread', lambda **kwargs: threads.append(_FakeThread(**kwargs)) or threads[-1])
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


def test_replace_selection_swaps_the_selected_text_and_records_undo():
    buf = Gtk.TextBuffer()
    buf.set_text('a płaszcz b')
    start = buf.get_iter_at_offset(2)
    end = buf.get_iter_at_offset(9)
    buf.select_range(start, end)

    class _Textbox:
        pass
    textbox = _Textbox()
    textbox.buffer = buf

    model = _make_model()
    model._replace_selection(textbox, 'sukmana')

    assert buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False) == 'a sukmana b'
    assert model.controller.main_controller.undo_controller.calls == ['start', 'stop']


def test_on_download_does_not_start_a_second_thread_while_one_is_in_flight(monkeypatch, tmp_path):
    monkeypatch.setattr(thesaurus_module, 'thesaurus_cache_dir', lambda: str(tmp_path))
    threads = []
    monkeypatch.setattr(thesaurus_module.threading, 'Thread', lambda **kwargs: threads.append(_FakeThread(**kwargs)) or threads[-1])
    model = _make_model()

    model._on_download(None, 'pl_PL')
    model._on_download(None, 'pl_PL')

    assert len(threads) == 1
    assert threads[0].started
