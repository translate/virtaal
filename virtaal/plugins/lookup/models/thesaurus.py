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
to matter (English's real thesaurus, at time of writing: ~1.5s to
parse - it's the largest of the bundled languages, at 18MB raw).
Once parsed, a locale's thesaurus is kept in memory for the rest of
the session - every subsequent look-up is then an in-memory dict
access, not worth optimising further (e.g. via the .idx files mythes'
own C++ library uses for random-access reads - real folders don't
reliably ship one anyway, en's own included, and it would only ever
help this one-time parse, not the free lookups after it). Nothing
currently evicts an old entry once loaded - English alone parses to
~150MB resident; a session that looks up several language pairs
keeps every one of them in memory for as long as the app runs.

Also downloads proactively on source/target-lang-changed (which fires
on opening a file too, not just an explicit language-picker change),
same trigger virtaal.support.dictionary_download_watcher already uses
for spell-check dictionaries - by the time anyone actually right-clicks
a word, the download has usually already finished in the background.

A locale's availability is checked against asset_manifest.py's cached
manifest first - an instant local lookup once cached, not the live
tree + xcu fetch every locale used to need. Once a locale is confirmed
to have no thesaurus at all, no menu item is shown for it again this
session, rather than offering a "Download" button that would only ever
fail. Only falls back to the live tree + xcu check when the manifest
itself was never fetched successfully - that live check
(dictionary_source.fetch_dictionary_tree/fetch_xcu/find_dictionary)
stays synchronous, run in its own thread (below); only the actual file
fetch, once folder/files are known either way, goes through
thesaurus_downloader.py's async HTTPClient chain instead of a second
blocking call in that same thread."""

import logging
import os
import re
import threading

from gi.repository import GLib, Gtk

from virtaal.common import pan_app
from virtaal.support import asset_manifest as asset_manifest_module
from virtaal.support import mythes
from virtaal.support.asset_manifest import AssetManifest
from virtaal.support.dictionary_source import (
    fetch_dictionary_tree,
    fetch_xcu,
    find_dictionary,
    list_dictionary_folders,
)
from virtaal.support.thesaurus_downloader import ThesaurusDownloader

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


# MyThes' own qualifier convention, e.g. "bantam (similar term)" or
# French's "vieux (familier)" - present across languages, always with
# a preceding space, and common enough in English's own thesaurus to
# be the majority case (~54% of all synonym occurrences), not an edge
# case. Requiring the space matters: French also glues a reflexive
# marker directly onto some verbs with no space ("plier(se)", for "se
# plier") - real, different from a qualifier, and not something this
# should touch.
_WORD_ANNOTATION_RE = re.compile(r'\s+\([^)]*\)$')


class LookupModel(BaseLookupModel):
    """Look up the selected word in a downloaded thesaurus."""

    __gtype_name__ = 'ThesaurusLookupModel'
    #l10n: plugin name
    display_name = _('Thesaurus')
    description = _('Look up synonyms for the selected word')
    TOP_LEVEL = True

    # INITIALIZERS #
    def __init__(self, internal_name, controller, asset_manifest=None, schedule_after_idle_lull=None,
                 downloader_factory=None):
        self.controller = controller
        self.internal_name = internal_name
        self._asset_manifest = asset_manifest
        self._schedule_after_idle_lull = schedule_after_idle_lull or asset_manifest_module.schedule_after_idle_lull
        self._downloader_factory = downloader_factory or ThesaurusDownloader
        self._thesauruses = {}  # locale_code -> parsed {word: meanings}
        self._checking = set()  # locale_codes: availability check in flight
        self._unavailable = set()  # locale_codes confirmed to have no thesaurus at all
        self._downloading = set()  # locale_codes with a download in flight
        self._parsing = set()  # locale_codes with a background parse in flight
        self._parse_failed = set()  # locale_codes whose cached .dat failed to parse
        self._auto_tried = set()  # locale_codes an automatic check/download was already attempted for

        lang_controller = self.controller.main_controller.lang_controller
        lang_controller.connect('source-lang-changed', self._on_lang_changed)
        lang_controller.connect('target-lang-changed', self._on_lang_changed)
        if lang_controller.source_lang:
            self._maybe_auto_download(lang_controller.source_lang.code)
        if lang_controller.target_lang:
            self._maybe_auto_download(lang_controller.target_lang.code)

    def _get_asset_manifest(self):
        if self._asset_manifest is None:
            self._asset_manifest = AssetManifest()
        return self._asset_manifest

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

        if locale_code in self._unavailable:
            return []

        if locale_code in self._checking:
            #l10n: shown in the selected text's right-click menu while checking whether a thesaurus exists for this language at all
            return [self._create_status_item(_('Checking for thesaurus…'))]

        if locale_code in self._downloading:
            #l10n: %(language)s is a language name, e.g. "Afrikaans"
            return [self._create_status_item(_('Downloading %(language)s thesaurus…') % {'language': _language_name(locale_code)})]

        if self._maybe_start_parse(locale_code):
            return [self._create_status_item(_('Loading thesaurus…'))]

        return [self._create_download_item(locale_code)]

    def _create_status_item(self, label):
        item = Gtk.MenuItem(label=label)
        item.set_sensitive(False)
        return item

    def _create_download_item(self, locale_code):
        #l10n: %(language)s is a language name, e.g. "Afrikaans"
        item = Gtk.MenuItem(label=_('Download %(language)s thesaurus…') % {'language': _language_name(locale_code)})
        item.connect('activate', self._on_download, locale_code)
        return item

    def _create_synonym_item(self, meanings, textbox):
        #l10n: The menu entry offering synonyms for the selected word.
        item = Gtk.MenuItem(label=_('Synonyms'))
        submenu = Gtk.Menu()
        for pos, synonyms in meanings:
            if pos and pos != '-':
                header = Gtk.MenuItem(label=pos)
                header.set_sensitive(False)
                submenu.append(header)
            for synonym in synonyms:
                # Keep the annotation in the label (see
                # _WORD_ANNOTATION_RE above) but never insert it.
                word = _WORD_ANNOTATION_RE.sub('', synonym)
                synonym_item = Gtk.MenuItem(label=synonym)
                synonym_item.connect('activate', self._on_insert_synonym, word, textbox)
                submenu.append(synonym_item)
        item.set_submenu(submenu)
        return item

    def _replace_selection(self, textbox, synonym):
        # Source textboxes are only set non-editable at the widget
        # level (set_editable(False)) - that blocks interactive
        # typing, not a direct buffer.insert()/delete() call like
        # this one, so it has to be checked explicitly here too.
        if textbox.role != 'target':
            return
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
        # A programmatic buf.insert()/delete() doesn't fire GTK's own
        # begin/end-user-action bracket the way interactive typing
        # does, which is what normally drives TextBox's own "changed"
        # signal (see textbox.py's _on_end_user_action) - without this,
        # the edit never reaches the document-modified tracking at all.
        # Same fix termview.py's own suggestion-insert already uses.
        textbox.emit('changed')

    def _maybe_auto_download(self, locale_code):
        locale_code = locale_code.replace('-', '_')
        if locale_code in self._auto_tried:
            return
        self._auto_tried.add(locale_code)
        if _cached_dat_path(locale_code) is not None:
            self._maybe_start_parse(locale_code)
            return
        self._get_asset_manifest().ensure_fresh(
            on_done=lambda: self._after_manifest_fresh(locale_code))

    def _after_manifest_fresh(self, locale_code):
        manifest = self._get_asset_manifest()
        entry = manifest.get('thesaurus', locale_code)
        if entry is None:
            if not manifest.has_data():
                return self._start_check(locale_code)
            self._unavailable.add(locale_code)  # manifest is authoritative - genuinely nothing for this locale
            return
        # Same idle-lull gate dictionary/autocorrect downloads already
        # use for a manifest-known download - live discovery (below,
        # only used when the manifest itself was never fetched) stays
        # unthrottled, so a first-ever encounter still downloads
        # promptly.
        self._schedule_after_idle_lull(
            lambda: self._start_download(locale_code, entry['folder'], [f['name'] for f in entry['files']]))

    def _maybe_start_parse(self, locale_code):
        """Starts a background parse of locale_code's cached .dat if
        one isn't already loaded, in flight, or previously failed.
        Returns True if a parse is now in flight (already was, or
        just started) - callers use that to decide whether to show a
        "Loading…" item."""
        if locale_code in self._thesauruses or locale_code in self._parse_failed:
            return False
        if locale_code in self._parsing:
            return True
        dat_path = _cached_dat_path(locale_code)
        if dat_path is None:
            return False
        self._parsing.add(locale_code)
        threading.Thread(target=self._parse, args=(locale_code, dat_path), daemon=True).start()
        return True

    def _start_check(self, locale_code):
        if locale_code in self._checking or locale_code in self._downloading:
            return
        self._parse_failed.discard(locale_code)
        self._checking.add(locale_code)
        threading.Thread(target=self._check, args=(locale_code,), daemon=True).start()

    def _check(self, locale_code):
        try:
            tree = fetch_dictionary_tree()
            folders = list_dictionary_folders(tree)
            match = find_dictionary(locale_code, folders, fetch_xcu, dict_format='DICT_THES')
        except Exception as e:
            # Same as dictionary_downloader.py's own DEBUG-level
            # logging for this - a failed background network check
            # must never surface as an application error, including
            # in a build-verification log-content check.
            logging.debug('Thesaurus availability check failed for %s: %s', locale_code, e)
            GLib.idle_add(self._checking.discard, locale_code)
            return
        if match is None:
            GLib.idle_add(self._on_unavailable, locale_code)
        else:
            folder, files = match
            GLib.idle_add(self._on_available, locale_code, folder, files)

    def _on_unavailable(self, locale_code):
        self._checking.discard(locale_code)
        if locale_code in self._downloading:
            return  # the manifest path already resolved this while this live check was still in flight
        self._unavailable.add(locale_code)

    def _on_available(self, locale_code, folder, files):
        self._checking.discard(locale_code)
        self._start_download(locale_code, folder, files)

    def _start_download(self, locale_code, folder, files):
        # A live check (via _on_download) and the manifest path
        # (_after_manifest_fresh) can both resolve for the same locale
        # during the manifest's own idle-lull-gated refresh window -
        # whichever gets here first wins, the other is a no-op.
        if locale_code in self._downloading:
            return
        self._downloading.add(locale_code)
        downloader = self._downloader_factory(
            locale_code, on_done=lambda success: self._on_download_finished(locale_code, success),
            target_dir=os.path.join(thesaurus_cache_dir(), locale_code))
        downloader.start_with_known_files(folder, files)

    def _on_download_finished(self, locale_code, succeeded):
        self._downloading.discard(locale_code)
        if succeeded:
            self._maybe_start_parse(locale_code)

    def _parse(self, locale_code, dat_path):
        try:
            with open(dat_path, 'rb') as f:
                thesaurus = mythes.parse_thesaurus(f.read())
        except Exception as e:
            logging.debug('Thesaurus parsing failed for %s: %s', locale_code, e)
            GLib.idle_add(self._on_parse_failed, locale_code)
            return
        GLib.idle_add(self._on_parsed, locale_code, thesaurus)

    def _on_parse_failed(self, locale_code):
        self._parsing.discard(locale_code)
        self._parse_failed.add(locale_code)

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
