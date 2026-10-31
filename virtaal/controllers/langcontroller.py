#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
import os

from gi.repository import GObject

from virtaal.common import GObjectWrapper, pan_app
from virtaal.models.langmodel import LanguageModel

from .basecontroller import BaseController


class LanguageController(BaseController):
    """
    The logic behind language management in Virtaal.
    """

    __gtype_name__ = 'LanguageController'
    __gsignals__ = {
        'source-lang-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'target-lang-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'dictionary-installed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    NUM_RECENT = 5
    """The number of recent language pairs to save/display."""

    # INITIALIZERS #
    def __init__(self, main_controller):
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.main_controller.lang_controller = self
        self.lang_identifier = None
        self.new_langs = []
        self._init_langs()
        self.recent_pairs = self._load_recent()

        self.main_controller.store_controller.connect('store-loaded', self._on_store_loaded)
        self.main_controller.connect('quit', self._on_quit)
        self.connect('source-lang-changed', self._on_lang_changed)
        self.connect('target-lang-changed', self._on_lang_changed)

        self.view = None

    def _init_langs(self):
        try:
            self._source_lang = LanguageModel(pan_app.settings.language['sourcelang'])
        except Exception:
            self._source_lang = None

        try:
            self._target_lang = LanguageModel(pan_app.settings.language['targetlang'])
        except Exception:
            self._target_lang = None

        # Load previously-saved (new) languages
        filename = os.path.join(pan_app.get_config_dir(), 'langs.ini')
        if os.path.isfile(filename):
            languages = {}
            for code, info in pan_app.load_config(filename).items():
                try:
                    languages[code] = (info['name'], int(info['nplurals']), info['plural'])
                except (KeyError, ValueError):
                    # Skipped, not fatal: this runs at start-up (#4331).
                    logging.warning('Ignoring unreadable language %r in %s', code, filename)
            LanguageModel.languages.update(languages)


    # ACCESSORS #
    def _get_source_lang(self):
        return self._source_lang
    def _set_source_lang(self, lang):
        if isinstance(lang, str):
            lang = LanguageModel(lang)
        if not lang or lang == self._source_lang:
            return
        self._source_lang = lang
        self.emit('source-lang-changed', self._source_lang.code)
    source_lang = property(_get_source_lang, _set_source_lang)

    def _get_target_lang(self):
        return self._target_lang
    def _set_target_lang(self, lang):
        if isinstance(lang, str):
            lang = LanguageModel(lang)
        if not lang or lang == self._target_lang:
            return
        self._target_lang = lang
        self.emit('target-lang-changed', self._target_lang.code)
    target_lang = property(_get_target_lang, _set_target_lang)

    def set_language_pair(self, srclang, tgtlang):
        if isinstance(srclang, str):
            srclang = LanguageModel(srclang)
        if isinstance(tgtlang, str):
            tgtlang = LanguageModel(tgtlang)

        pair = (srclang, tgtlang)
        if pair in self.recent_pairs:
            self.recent_pairs.remove(pair)

        self.recent_pairs.insert(0, pair)
        self.recent_pairs = self.recent_pairs[:self.NUM_RECENT]

        self.source_lang = srclang
        self.target_lang = tgtlang
        self.view.update_recent_pairs()
        if self.source_lang == self.target_lang:
            self.view.notify_same_langs()

        self._store_language_pair()
        pan_app.settings.write()


    # METHODS #
    def get_target_nplurals(self):
        """The number of plural forms to edit: the open file's own when it
            declares them, else the target language's."""
        store = self.main_controller.store_controller.get_store()
        declared = store and store.get_declared_nplurals()
        return declared or self.target_lang.nplurals or self.main_controller.store_controller.get_nplurals()

    def get_detected_langs(self):
        store = self.main_controller.store_controller.store
        if not store:
            return None

        srccode = store.get_source_language()
        tgtcode = store.get_target_language()
        if not (srccode and tgtcode):
            if not self.lang_identifier:
                from translate.lang.identify import LanguageIdentifier
                self.lang_identifier = LanguageIdentifier()
            if not srccode:
                srccode = self.lang_identifier.identify_source_lang(store.get_units())
            if not tgtcode:
                tgtcode = self.lang_identifier.identify_target_lang(store.get_units())
        srclang = tgtlang = None
        if srccode:
            srclang = LanguageModel(srccode)
        if tgtcode:
            tgtlang = LanguageModel(tgtcode)

        return srclang, tgtlang

    def _load_recent(self):
        recent_pairs = []
        for pair in pan_app.settings.language['recentlangs'].split('|'):
            codes = pair.split(',')
            # A malformed pair is skipped: this runs at every start-up (#4331).
            if len(codes) == 2 and all(codes):
                recent_pairs.append((LanguageModel(codes[0]), LanguageModel(codes[1])))
        return recent_pairs

    def save_recent(self):
        # A code containing a separator can't be read back.
        pairs = [','.join([src.code, tgt.code]) for (src, tgt) in self.recent_pairs
                 if not any(sep in src.code + tgt.code for sep in ',|')]
        recent = '|'.join(pairs)
        pan_app.settings.language['recentlangs'] = recent


    # EVENT HANDLERS #
    def _on_lang_changed(self, sender, code):
        self.save_recent()
        if self.source_lang == self.target_lang:
            self.view.notify_same_langs()
        else:
            self.view.notify_diff_langs()

    def _on_quit(self, main_controller):
        self._store_language_pair()
        self.save_new_langs()

    def _store_language_pair(self):
        pan_app.settings.language['sourcelang'] = self.source_lang.code
        pan_app.settings.language['targetlang'] = self.target_lang.code

    def save_new_langs(self):
        """Write languages added or edited in Virtaal to langs.ini."""
        if not self.new_langs:
            return

        langs = {}
        filename = os.path.join(pan_app.get_config_dir(), 'langs.ini')
        if os.path.isfile(filename):
            langs = pan_app.load_config(filename)

        newlangdict = {}
        for code in self.new_langs:
            newlangdict[code] = {}
            newlangdict[code]['name'] = LanguageModel.languages[code][0]
            newlangdict[code]['nplurals'] = LanguageModel.languages[code][1]
            newlangdict[code]['plural'] = LanguageModel.languages[code][2]
        langs.update(newlangdict)

        pan_app.save_config(filename, langs)

    def _on_store_loaded(self, store_controller):
        if not self.view:
            from virtaal.views.langview import LanguageView
            self.view = LanguageView(self)
            self.view.show()
        srclang = store_controller.store.get_source_language() or self.source_lang.code
        tgtlang = store_controller.store.get_target_language() or self.target_lang.code
        self.set_language_pair(srclang, tgtlang)
