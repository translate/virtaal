#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The terminology models and the local file view, built through their
real constructors on a real main controller."""

import logging
import os
import time
from types import SimpleNamespace

import pytest
from gi.repository import Gdk, Gtk
from translate.storage.placeables.terminology import TerminologyPlaceable

from virtaal.common import pan_app
from virtaal.common.platform import platform
from virtaal.controllers.placeablescontroller import PlaceablesController
from virtaal.plugins.terminology.models import autoterm, localfile, pontoon
from virtaal.plugins.terminology.models.localfile import localfileview
from virtaal.plugins.terminology.termcontroller import TerminologyController
from virtaal.support.httpclient import HTTPClient
from virtaal.test.test_scaffolding import TestScaffolding
from virtaal.views import baseview

TERMS_PO = '''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "file"
msgstr "leer"
'''
ADD_TERM_PATH = "<Virtaal>/Terminology/Add Term"


class TestTerminologyModelsStartup(TestScaffolding):
    def setup_class(self):
        TestScaffolding.setup_class(self)
        PlaceablesController(self.main_controller)
        # Every model is built by the tests themselves.
        self.term_controller = TerminologyController(
            self.main_controller, {'disabled_models': ['localfile', 'autoterm', 'pontoon']})
        self.unit_controller.load_unit(self.trans_store.units[1])
        self.unit_view = self.unit_controller.view

    @pytest.fixture(autouse=True)
    def _isolate(self, monkeypatch, tmp_path):
        monkeypatch.setattr(pan_app, 'get_config_dir', lambda: str(tmp_path))
        # Other tests destroy dialogs built from the shared builders.
        monkeypatch.setattr(baseview, '_builders', {})
        monkeypatch.setitem(pan_app.settings.language, 'recentlangs',
                            pan_app.settings.language['recentlangs'])
        self.requests = []
        monkeypatch.setattr(HTTPClient, 'get', lambda client, url, callback, etag=None, **kwargs:
                            self.requests.append((url, etag, kwargs)))
        langs = self.lang_controller
        # Only the full app builds the language controller's view.
        monkeypatch.setattr(langs, 'view', SimpleNamespace(
            update_recent_pairs=lambda: None, notify_same_langs=lambda: None,
            notify_diff_langs=lambda: None))
        for name in ('_source_lang', '_target_lang', 'recent_pairs'):
            monkeypatch.setattr(langs, name, getattr(langs, name))
        matchers = list(TerminologyPlaceable.matchers)
        self.models = []
        yield
        for model in self.models:
            model.destroy()
        TerminologyPlaceable.matchers[:] = matchers

    def _local_model(self, tmp_path, monkeypatch, files=1):
        paths = []
        for i in range(files):
            path = tmp_path / ('terms%d.po' % i)
            path.write_text(TERMS_PO)
            paths.append(str(path))
        monkeypatch.setitem(localfile.TerminologyModel.default_config, 'extendfile', paths[0])
        (tmp_path / 'terminology.ini').write_text(
            '[localfile]\nfiles = %s\nextendfile = %s\n' % (','.join(paths), paths[-1]))
        model = localfile.TerminologyModel('localfile', self.term_controller)
        self.models.append(model)
        return model, paths

    def _web_model(self, module, tmp_path, monkeypatch):
        termdir = tmp_path / module.__name__.rsplit('.', 1)[-1]
        monkeypatch.setattr(module.TerminologyModel, 'TERMDIR', str(termdir))
        model = module.TerminologyModel(module.__name__.rsplit('.', 1)[-1], self.term_controller)
        self.models.append(model)
        return model, termdir

    # Local files #

    def test_local_files_are_loaded_into_a_terminology_matcher(self, tmp_path, monkeypatch):
        model, paths = self._local_model(tmp_path, monkeypatch)

        assert model.config['files'] == paths
        assert [len(store.units) for store in model.stores] == [2]
        assert model.matcher in TerminologyPlaceable.matchers

    def test_reloading_local_files_replaces_the_matcher_and_skips_blank_names(self, tmp_path, monkeypatch):
        model, paths = self._local_model(tmp_path, monkeypatch)
        old_matcher = model.matcher
        model.config['files'] = ['', paths[0]]

        model.load_files()

        assert len(model.stores) == 1
        assert old_matcher not in TerminologyPlaceable.matchers
        assert model.matcher in TerminologyPlaceable.matchers

    def test_a_configured_file_that_has_gone_is_an_empty_store(self, tmp_path, monkeypatch):
        model, paths = self._local_model(tmp_path, monkeypatch)
        model.config['files'] = paths + [str(tmp_path / 'gone.po')]

        model.load_files()

        assert [len(store.units) for store in model.stores] == [2, 1]

    def test_get_store_for_an_unknown_filename_is_none(self, tmp_path, monkeypatch):
        model, _paths = self._local_model(tmp_path, monkeypatch)

        assert model.get_store_for_filename(str(tmp_path / 'other.po')) is None

    def test_destroying_the_local_model_removes_its_matcher_and_menu_items(self, tmp_path, monkeypatch):
        model, _paths = self._local_model(tmp_path, monkeypatch)
        self.models.remove(model)
        edit_menu = model.view.menu

        model.destroy()

        assert model.matcher not in TerminologyPlaceable.matchers
        assert model.view.mnu_add_term not in edit_menu.get_children()
        assert model.view.mnu_select_files not in edit_menu.get_children()

    # The local file view's menus and shortcut #

    def test_the_edit_menu_gets_terminology_items(self, tmp_path, monkeypatch):
        model, _paths = self._local_model(tmp_path, monkeypatch)
        view = model.view

        edit_items = view.menu.get_children()
        assert view.mnu_select_files in edit_items
        assert view.mnu_add_term in edit_items
        assert view.mnu_add_term.get_accel_path() == ADD_TERM_PATH
        found, key = Gtk.AccelMap.lookup_entry(ADD_TERM_PATH)
        assert found
        # GTK's macOS backend turns Ctrl into Cmd.
        primary = Gdk.ModifierType.META_MASK if platform.is_mac else Gdk.ModifierType.CONTROL_MASK
        assert (key.accel_key, key.accel_mods) == (Gdk.KEY_t, primary)

    def test_an_edit_menu_without_an_accel_group_gets_one(self, tmp_path, monkeypatch):
        edit_menu = self.main_controller.view.gui.get_object('menuitem_edit').get_submenu()
        original = edit_menu.get_accel_group()
        edit_menu.set_accel_group(None)
        try:
            model, _paths = self._local_model(tmp_path, monkeypatch)

            accel_group = edit_menu.get_accel_group()
            assert accel_group is not None
            assert accel_group is not original
            assert accel_group in Gtk.accel_groups_from_object(self.main_controller.view.main_window)
        finally:
            edit_menu.set_accel_group(original)

    def test_the_menu_items_open_their_dialogs_over_the_main_window(self, tmp_path, monkeypatch):
        opened = []
        monkeypatch.setattr(localfileview.TermAddDialog, 'run',
                            lambda dialog, parent=None: opened.append(('add', parent)))
        monkeypatch.setattr(localfileview.FileSelectDialog, 'run',
                            lambda dialog, parent=None: opened.append(('files', parent)))
        model, _paths = self._local_model(tmp_path, monkeypatch)
        main_window = self.main_controller.view.main_window

        model.view.mnu_add_term.activate()
        model.view.mnu_select_files.activate()

        assert opened == [('add', main_window), ('files', main_window)]

    def test_a_second_view_reuses_the_existing_menu_items(self, tmp_path, monkeypatch):
        model, _paths = self._local_model(tmp_path, monkeypatch)

        other = localfileview.LocalFileView(model)
        try:
            assert other.mnu_add_term is model.view.mnu_add_term
            assert other.mnu_select_files is model.view.mnu_select_files
        finally:
            other._signal_tracker.disconnect_all()

    # The local file view's textbox context menus #

    def _add_term_items(self, textbox):
        menu = Gtk.Menu()
        textbox.emit('populate-popup', menu)
        return [item.get_label() for item in menu.get_children()
                if isinstance(item, Gtk.MenuItem) and (item.get_label() or '').startswith('Add Term')]

    def test_source_and_target_context_menus_offer_the_selection_as_a_term(self, tmp_path, monkeypatch):
        self._local_model(tmp_path, monkeypatch)

        for textbox in (self.unit_view.sources[0], self.unit_view.targets[0]):
            textbox.buffer.select_range(*textbox.buffer.get_bounds())
            text = textbox.get_text()

            assert self._add_term_items(textbox) == ['Add Term "%s"…' % text]

    def test_textboxes_created_later_get_the_context_menu_item(self, tmp_path, monkeypatch):
        widgets = self.unit_view._widgets
        sources, targets = widgets['sources'], widgets['targets']
        monkeypatch.setitem(widgets, 'sources', [])
        monkeypatch.setitem(widgets, 'targets', [])
        self._local_model(tmp_path, monkeypatch)
        widgets['sources'], widgets['targets'] = sources, targets

        self.unit_view.emit('sources-created', sources)
        self.unit_view.emit('targets-created', targets)

        for textbox in (sources[0], targets[0]):
            textbox.buffer.select_range(*textbox.buffer.get_bounds())
            assert len(self._add_term_items(textbox)) == 1

    # Choosing terminology files #

    def _filter_matches(self, file_filter, name):
        info = Gtk.FileFilterInfo()
        info.contains = Gtk.FileFilterFlags.FILENAME | Gtk.FileFilterFlags.DISPLAY_NAME
        info.filename = '/tmp/' + name
        info.display_name = name
        return file_filter.filter(info)

    def test_the_add_files_chooser_filters_on_every_supported_format(self, tmp_path, monkeypatch):
        model, _paths = self._local_model(tmp_path, monkeypatch)

        chooser = model.view.fileselect.add_chooser
        filters = chooser.list_filters()

        names = [f.get_name() for f in filters]
        assert names[0] == 'All Supported Files'
        assert names[-1] == 'All Files'
        assert chooser.get_select_multiple()
        supported = filters[0]
        for name in ('terms.po', 'terms.po.gz', 'terms.tbx', 'terms.xlf'):
            assert self._filter_matches(supported, name), name
        po_filters = [f for f in filters[1:-1] if self._filter_matches(f, 'terms.po.bz2')]
        assert po_filters
        assert not self._filter_matches(po_filters[0], 'terms.tbx')

    # Adding a term #

    def test_add_term_starts_from_the_selected_source_and_target_text(self, tmp_path, monkeypatch):
        model, paths = self._local_model(tmp_path, monkeypatch, files=2)
        source, target = self.unit_view.sources[0], self.unit_view.targets[0]
        source.buffer.select_range(source.buffer.get_start_iter(), source.buffer.get_iter_at_offset(8))
        target.buffer.select_range(target.buffer.get_start_iter(), target.buffer.get_iter_at_offset(3))
        dialog = model.view.addterm

        dialog.reset()

        assert dialog.ent_source.get_text() == source.get_text(0, 8).strip()
        assert dialog.ent_target.get_text() == target.get_text(0, 3).strip()
        langs = self.lang_controller
        assert langs.source_lang.name in dialog.lbl_srclang.get_text()
        assert langs.target_lang.name in dialog.lbl_tgtlang.get_text()
        assert [row[0] for row in dialog.lst_termfiles] == paths
        assert dialog.cmb_termfile.get_active() == 1

    def test_add_term_starts_empty_without_a_selection(self, tmp_path, monkeypatch):
        model, _paths = self._local_model(tmp_path, monkeypatch)
        for textbox in self.unit_view.sources + self.unit_view.targets:
            textbox.buffer.place_cursor(textbox.buffer.get_start_iter())
        dialog = model.view.addterm

        dialog.reset()

        assert dialog.ent_source.get_text() == ''
        assert dialog.ent_target.get_text() == ''

    # Pontoon and the localization terminology downloads #

    @pytest.mark.parametrize('module', [pontoon, autoterm])
    def test_a_download_model_starts_with_an_empty_matcher_and_fetches_terms(self, module, tmp_path, monkeypatch):
        self.lang_controller.set_language_pair('en', 'af')

        model, termdir = self._web_model(module, tmp_path, monkeypatch)

        assert termdir.is_dir()
        assert model.matcher in TerminologyPlaceable.matchers
        assert len(model.store.units) == 0
        assert [url for url, _etag, _kwargs in self.requests] == [
            module.TerminologyModel._l10n_URL % {'srclang': 'en', 'tgtlang': 'af'}]

    @pytest.mark.parametrize('module', [pontoon, autoterm])
    def test_a_download_model_follows_a_target_language_change(self, module, tmp_path, monkeypatch):
        self.lang_controller.set_language_pair('en', 'af')
        model, _termdir = self._web_model(module, tmp_path, monkeypatch)
        del self.requests[:]

        self.lang_controller.target_lang = 'de'

        assert model.target_lang == 'de'
        assert [url for url, _etag, _kwargs in self.requests] == [
            module.TerminologyModel._l10n_URL % {'srclang': 'en', 'tgtlang': 'de'}]

    def test_pontoon_logs_a_failed_download_when_debugging(self, tmp_path, monkeypatch):
        monkeypatch.setattr(logging.root, 'level', logging.DEBUG)
        self.lang_controller.set_language_pair('en', 'af')

        self._web_model(pontoon, tmp_path, monkeypatch)

        assert 'error_callback' in self.requests[0][2]

    def test_pontoon_logs_why_a_download_failed(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(logging.root, 'level', logging.DEBUG)
        self.lang_controller.set_language_pair('en', 'af')
        self._web_model(pontoon, tmp_path, monkeypatch)
        url, _etag, kwargs = self.requests[0]

        with caplog.at_level(logging.DEBUG):
            kwargs['error_callback'](SimpleNamespace(status=404), None)

        assert 'Could not get %s: status 404' % url in caplog.text

    def test_pontoon_sends_the_etag_of_an_expired_download(self, tmp_path, monkeypatch):
        self.lang_controller.set_language_pair('en', 'af')
        termdir = tmp_path / 'pontoon'
        termdir.mkdir()
        old = termdir / 'en__af.tbx'
        old.write_bytes(b'')
        stale = time.time() - 4 * 24 * 60 * 60
        os.utime(old, (stale, stale))
        (tmp_path / 'terminology.ini').write_text('[pontoon]\nen__af.tbx = abc123\n')

        self._web_model(pontoon, tmp_path, monkeypatch)

        assert [etag for _url, etag, _kwargs in self.requests] == ['abc123']

    def test_pontoon_reads_a_recent_po_download_without_fetching(self, tmp_path, monkeypatch):
        # Downloads from the earlier terminology server were PO files.
        self.lang_controller.set_language_pair('en', 'af')
        termdir = tmp_path / 'pontoon'
        termdir.mkdir()
        (termdir / 'en__af.po').write_text(TERMS_PO)

        model, _termdir = self._web_model(pontoon, tmp_path, monkeypatch)

        assert self.requests == []
        assert [unit.source for unit in model.store.units if unit.source] == ['file']

    def test_destroying_a_download_model_saves_its_config(self, tmp_path, monkeypatch):
        self.lang_controller.set_language_pair('en', 'af')
        model, _termdir = self._web_model(pontoon, tmp_path, monkeypatch)
        self.models.remove(model)
        model.config['en__af.tbx'] = 'etag-1'

        model.destroy()

        assert 'etag-1' in (tmp_path / 'terminology.ini').read_text()
