#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Right-click synonym look-up, using LibreOffice's own MyThes
thesaurus data (see virtaal.support.mythes and .dictionary_source's
DICT_THES support).

Neither downloading nor parsing a locale's thesaurus ever happens
inline from create_menu_items() (called synchronously while building
a context menu, on the UI thread) - both are real work large enough
to matter (English's real thesaurus, at time of writing: ~250-340ms
to parse). Once parsed, a locale's
thesaurus is kept in memory for the rest of the session - every
subsequent look-up is then an in-memory dict access, not worth
optimising further (e.g. via the .idx files mythes' own C++ library
uses for random-access reads - real folders don't reliably ship one
anyway, en's own included, and it would only ever help this one-time
parse, not the free lookups after it).

Also downloads proactively on source/target-lang-changed (which fires
on opening a file too, not just an explicit language-picker change),
same trigger virtaal.support.dictionary_download_watcher already uses
for spell-check dictionaries - by the time anyone actually right-clicks
a word, the download has usually already finished in the background.

A locale's availability is checked (a light tree + xcu fetch, no big
file) before ever downloading anything - once a locale is confirmed to
have no thesaurus in the repo at all, no menu item is shown for it
again this session, rather than offering a "Download" button that
would only ever fail."""

import logging
import os
import threading

from gi.repository import GLib, Gtk

from virtaal.common import pan_app
from virtaal.support import mythes
from virtaal.support.dictionary_source import (
    download_dictionary,
    fetch_dictionary_tree,
    fetch_xcu,
    find_dictionary,
    list_dictionary_folders,
)

try:
    from virtaal.plugins.lookup.models.baselookupmodel import BaseLookupModel
except ImportError:
    from virtaal_plugins.lookup.models.baselookupmodel import BaseLookupModel


def thesaurus_cache_dir():
    return os.path.join(pan_app.get_config_dir(), 'thesaurus')


def _cached_dat_path(locale_code):
    path = os.path.join(thesaurus_cache_dir(), locale_code)
    if not os.path.isdir(path):
        return None
    for name in os.listdir(path):
        if name.endswith('.dat'):
            return os.path.join(path, name)
    return None


def _language_name(locale_code):
    from virtaal.models.langmodel import LanguageModel
    return LanguageModel(locale_code).name


class LookupModel(BaseLookupModel):
    """Look up the selected word in a downloaded thesaurus."""

    __gtype_name__ = 'ThesaurusLookupModel'
    #l10n: plugin name
    display_name = _('Thesaurus')
    description = _('Look up synonyms for the selected word')
    TOP_LEVEL = True

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.controller = controller
        self.internal_name = internal_name
        self._thesauruses = {}  # locale_code -> parsed {word: meanings}
        self._checking = set()  # locale_codes: availability check in flight
        self._unavailable = set()  # locale_codes confirmed to have no thesaurus at all
        self._downloading = set()  # locale_codes with a download in flight
        self._parsing = set()  # locale_codes with a background parse in flight
        self._auto_tried = set()  # locale_codes an automatic check/download was already attempted for

        lang_controller = self.controller.main_controller.lang_controller
        lang_controller.connect('source-lang-changed', self._on_lang_changed)
        lang_controller.connect('target-lang-changed', self._on_lang_changed)
        if lang_controller.source_lang:
            self._maybe_auto_download(lang_controller.source_lang.code)
        if lang_controller.target_lang:
            self._maybe_auto_download(lang_controller.target_lang.code)

    # METHODS #
    def create_menu_items(self, query, role, srclang, tgtlang, textbox):
        word = query.strip().split(None, 1)[:1]
        if not word:
            return []
        word = word[0]
        locale_code = (srclang if role == 'source' else tgtlang).replace('-', '_')

        if locale_code in self._thesauruses:
            meanings = mythes.lookup(self._thesauruses[locale_code], word)
            if not meanings:
                return []
            return [self._create_synonym_item(meanings, textbox)]

        if locale_code in self._parsing:
            return [self._create_status_item(_('Loading thesaurus…'))]

        dat_path = _cached_dat_path(locale_code)
        if dat_path is not None:
            self._parsing.add(locale_code)
            threading.Thread(target=self._parse, args=(locale_code, dat_path), daemon=True).start()
            return [self._create_status_item(_('Loading thesaurus…'))]

        if locale_code in self._unavailable:
            return []

        if locale_code in self._checking:
            #l10n: shown in the selected text's right-click menu while checking whether a thesaurus exists for this language at all
            return [self._create_status_item(_('Checking for thesaurus…'))]

        if locale_code in self._downloading:
            #l10n: %(language)s is a language name, e.g. "Afrikaans"
            return [self._create_status_item(_('Downloading %(language)s thesaurus…') % {'language': _language_name(locale_code)})]

        return [self._create_download_item(locale_code)]

    def _create_status_item(self, label):
        item = Gtk.MenuItem(label)
        item.set_sensitive(False)
        return item

    def _create_download_item(self, locale_code):
        #l10n: %(language)s is a language name, e.g. "Afrikaans"
        item = Gtk.MenuItem(_('Download %(language)s thesaurus…') % {'language': _language_name(locale_code)})
        item.connect('activate', self._on_download, locale_code)
        return item

    def _create_synonym_item(self, meanings, textbox):
        #l10n: The menu entry offering synonyms for the selected word.
        item = Gtk.MenuItem(_('Synonyms'))
        submenu = Gtk.Menu()
        for pos, synonyms in meanings:
            if pos and pos != '-':
                header = Gtk.MenuItem(pos)
                header.set_sensitive(False)
                submenu.append(header)
            for synonym in synonyms:
                synonym_item = Gtk.MenuItem(synonym)
                synonym_item.connect('activate', self._on_insert_synonym, synonym, textbox)
                submenu.append(synonym_item)
        item.set_submenu(submenu)
        return item

    def _replace_selection(self, textbox, synonym):
        buf = textbox.buffer
        if not buf.get_has_selection():
            return
        start, end = (itr.get_offset() for itr in buf.get_selection_bounds())
        undo_controller = self.controller.main_controller.undo_controller
        undo_controller.record_start()
        start_iter = buf.get_iter_at_offset(start)
        end_iter = buf.get_iter_at_offset(end)
        buf.delete(start_iter, end_iter)
        buf.insert(start_iter, synonym)
        undo_controller.record_stop()

    def _maybe_auto_download(self, locale_code):
        locale_code = locale_code.replace('-', '_')
        if locale_code in self._auto_tried:
            return
        self._auto_tried.add(locale_code)
        if _cached_dat_path(locale_code) is not None:
            return
        self._start_check(locale_code)

    def _start_check(self, locale_code):
        if locale_code in self._checking or locale_code in self._downloading:
            return
        self._checking.add(locale_code)
        threading.Thread(target=self._check, args=(locale_code,), daemon=True).start()

    def _check(self, locale_code):
        try:
            tree = fetch_dictionary_tree()
            folders = list_dictionary_folders(tree)
            match = find_dictionary(locale_code, folders, fetch_xcu, dict_format='DICT_THES')
        except Exception:
            logging.exception('Thesaurus availability check failed for %s', locale_code)
            GLib.idle_add(self._checking.discard, locale_code)
            return
        if match is None:
            GLib.idle_add(self._on_unavailable, locale_code)
        else:
            GLib.idle_add(self._on_available, locale_code)

    def _on_unavailable(self, locale_code):
        self._checking.discard(locale_code)
        self._unavailable.add(locale_code)

    def _on_available(self, locale_code):
        self._checking.discard(locale_code)
        self._downloading.add(locale_code)
        threading.Thread(target=self._download, args=(locale_code,), daemon=True).start()

    def _download(self, locale_code):
        try:
            download_dictionary(locale_code, target_dir=os.path.join(thesaurus_cache_dir(), locale_code), dict_format='DICT_THES')
        except Exception:
            logging.exception('Thesaurus download failed for %s', locale_code)
        finally:
            GLib.idle_add(self._downloading.discard, locale_code)

    def _parse(self, locale_code, dat_path):
        try:
            with open(dat_path, 'rb') as f:
                thesaurus = mythes.parse_thesaurus(f.read())
        except Exception:
            logging.exception('Thesaurus parsing failed for %s', locale_code)
            GLib.idle_add(self._parsing.discard, locale_code)
            return
        GLib.idle_add(self._on_parsed, locale_code, thesaurus)

    def _on_parsed(self, locale_code, thesaurus):
        self._thesauruses[locale_code] = thesaurus
        self._parsing.discard(locale_code)

    # SIGNAL HANDLERS #
    def _on_lang_changed(self, _lang_controller, locale_code):
        self._maybe_auto_download(locale_code)

    def _on_download(self, menuitem, locale_code):
        self._start_check(locale_code)

    def _on_insert_synonym(self, menuitem, synonym, textbox):
        self._replace_selection(textbox, synonym)
