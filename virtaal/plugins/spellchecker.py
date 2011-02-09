#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2011 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import logging
import os
import os.path
import re
from gettext import dgettext
import gobject

from virtaal.common import pan_app
from virtaal.controllers.baseplugin import BasePlugin

if not pan_app.DEBUG:
    try:
        import psyco
    except:
        psyco = None
else:
    psyco = None

_dict_add_re = re.compile('Add "(.*)" to Dictionary')


class Plugin(BasePlugin):
    """A plugin to control spell checking.

    It can also download spell checkers on Windows."""

    display_name = _('Spell Checker')
    description = _('Check spelling and provide suggestions')
    version = 0.1

    _base_URL = 'http://dictionary.locamotion.org/hunspell/'
    _dict_URL = _base_URL + '%s.tar.bz2'
    _lang_list = 'languages.txt'

    # INITIALIZERS #
    def __init__(self, internal_name, main_controller):
        self.internal_name = internal_name

        # If these imports fail, the plugin is automatically disabled
        import gtkspell
        import enchant
        self.gtkspell = gtkspell
        self.enchant = enchant
        # languages that we've handled before:
        self._seen_languages = {}
        # languages supported by enchant:
        self._enchant_languages = self.enchant.list_languages()

        # HTTP clients (Windows only)
        self.clients = {}
        # downloadable languages (Windows only)
        self.languages = set()

        unit_view = main_controller.unit_controller.view
        self.unit_view = unit_view
        self._connect_id = self.unit_view.connect('textview-language-changed', self._on_unit_lang_changed)

        self._textbox_ids = []
        self._unitview_ids = []
        # For some reason the i18n of gtkspell doesn't work on Windows, so we
        # intervene. We also don't want the Languages submenu, so we remove it.
        if unit_view.sources:
            self._connect_to_textboxes(unit_view, unit_view.sources)
            srclang = main_controller.lang_controller.source_lang.code
            for textview in unit_view.sources:
                self._on_unit_lang_changed(unit_view, textview, srclang)
        else:
            self._unitview_ids.append(unit_view.connect('sources-created', self._connect_to_textboxes))
        if unit_view.targets:
            self._connect_to_textboxes(unit_view, unit_view.targets)
            tgtlang = main_controller.lang_controller.target_lang.code
            for textview in unit_view.targets:
                self._on_unit_lang_changed(unit_view, textview, tgtlang)
        else:
            self._unitview_ids.append(unit_view.connect('targets-created', self._connect_to_textboxes))

    def destroy(self):
        """Remove signal connections and disable spell checking."""
        for id in self._unitview_ids:
            self.unit_view.disconnect(id)
        for textbox, id in self._textbox_ids:
            textbox.disconnect(id)
        if getattr(self, '_connect_id', None):
            self.unit_view.disconnect(self._connect_id)
        for text_view in self.unit_view.sources + self.unit_view.targets:
            self._disable_checking(text_view)

    def _connect_to_textboxes(self, unitview, textboxes):
        for textbox in textboxes:
            self._textbox_ids.append((
                textbox,
                textbox.connect('populate-popup', self._on_populate_popup)
            ))


    # METHODS #

    def _build_client(self, url, clients_id, callback, error_callback=None):
        from virtaal.support.httpclient import HTTPClient
        client = HTTPClient()
        client.set_virtaal_useragent()
        self.clients[clients_id] = client
        if logging.root.level != logging.DEBUG:
            client.get(url, callback)
        else:
            def error_log(request, result):
                logging.debug('Could not get %s: status %d' % (url, request.status))
            client.get(url, callback, error_callback=error_log)

    def _download_checker(self, language):
        """A Windows-only way to obtain new dictionaries."""
        if 'APPDATA' not in os.environ:
            # We won't have an idea of where to save it, so let's give up now
            return
        if language in self.clients:
            # We already tried earlier, or started the process
            return
        if not self.languages:
            if self._lang_list not in self.clients:
                # We don't yet have a list of available languages
                url = self._base_URL + self._lang_list #index page listing all the dictionaries
                callback = lambda *args: self._process_index(language=language, *args)
                self._build_client(url, self._lang_list, callback)
                # self._process_index will call this again, so we can exit
            return

        language_to_download = None
        # People almost definitely want 'en_US' for 'en', so let's ensure
        # that we get that right:
        if language == 'en':
            language_to_download = 'en_US'
            self.clients[language] = None
        else:
            # Let's see if a dictionary is available for this language:
            for l in self.languages:
                if l == language or l.startswith(language+'_'):
                    self.clients[language] = None
                    logging.debug("Will use %s to spell check %s", l, language)
                    language_to_download = l
                    break
            else:
                # No dictionary available
                # Indicate that we never need to try this language:
                logging.debug("Found no suitable language for spell checking")
                self.clients[language] = None
                return

       # Now download the actual files after we have determined that it is
       # available
        callback = lambda *args: self._process_tarball(language=language, *args)
        url = self._dict_URL % language_to_download
        self._build_client(url, language, callback)


    def _tar_ok(self, tar):
        # TODO: Verify that the tarball is ok:
        # - only two files
        # - must be .aff and .dic
        # - language codes should be sane
        # - file sizes should be ok
        # - no directory structure
        return True

    def _ensure_dir(self, dir):
        if not os.path.isdir(dir):
            os.makedirs(dir)

    def _process_index(self, request, result, language=None):
        """Process the list of languages."""
        if request.status == 200 and not self.languages:
            self.languages = set(result.split())
            self._download_checker(language)
        else:
            logging.debug("Couldn't get list of spell checkers")
            #TODO: disable plugin

    def _process_tarball(self, request, result, language=None):
        # Indicate that we already tried and shouldn't try again later:
        self.clients[language] = None

        if request.status == 200:
            logging.debug('Got a dictionary')
            from cStringIO import StringIO
            import tarfile
            file_obj = StringIO(result)
            tar = tarfile.open(fileobj=file_obj)
            if not self._tar_ok(tar):
                return
            DICTDIR = os.path.join(os.environ['APPDATA'], 'enchant', 'myspell')
            self._ensure_dir(DICTDIR)
            tar.extractall(DICTDIR)
            self._seen_languages.pop(language, None)
            self._enchant_languages = self.enchant.list_languages()
            self.unit_view.update_languages()
        else:
            logging.debug("Couldn't get a dictionary. Status code: %d" % (request.status))

    def _disable_checking(self, text_view):
        """Disable checking on the given text_view."""
        if getattr(text_view, 'spell_lang', 'xxxx') is None:
            # No change necessary - already disabled
            return
        spell = None
        try:
            spell = self.gtkspell.get_from_text_view(text_view)
        except SystemError, e:
            # At least on Mandriva .get_from_text_view() sometimes returns
            # a SystemError without a description. Things seem to work fine
            # anyway, so let's ignore it and hope for the best.
            pass
        if not spell is None:
            spell.detach()
        text_view.spell_lang = None
    if psyco:
        psyco.cannotcompile(_disable_checking)


    # SIGNAL HANDLERS #
    def _on_unit_lang_changed(self, unit_view, text_view, language):
        if not self.gtkspell:
            return

        # enchant doesn't like anything except plain strings (bug 1852)
        language = str(language)

        if language == 'en':
            language = 'en_US'
        elif language == 'pt':
            language == 'pt_PT'

        if not language in self._seen_languages and not self.enchant.dict_exists(language):
            # Sometimes enchants *wants* a country code, other times it does not.
            # For the cases where it requires one, we look for the first language
            # code that enchant supports and use that one.
            for code in self._enchant_languages:
                if code.startswith(language+'_'):
                    self._seen_languages[language] = code
                    language = code
                    break
            else:
                #logging.debug('No code in enchant.list_languages() that starts with "%s"' % (language))

                # If we are on Windows, let's try to download a spell checker:
                if os.name == 'nt':
                    self._download_checker(language)
                    # If we get it, it will only be activated asynchronously
                    # later
                #TODO: packagekit on Linux?

                # We couldn't find a dictionary for "language", so we should make sure that we don't
                # have a spell checker for a different language on the text view. See bug 717.
                self._disable_checking(text_view)
                self._seen_languages[language] = None
                return

        language = self._seen_languages.get(language, language)
        if language is None:
            self._disable_checking(text_view)
            return

        if getattr(text_view, 'spell_lang', None) == language:
            # No change necessary - already enabled
            return
        gobject.idle_add(self._activate_checker, text_view, language, priority=gobject.PRIORITY_LOW)

    def _activate_checker(self, text_view, language):
        # All the expensive stuff in here called on idle. We mush also isolate
        # this away from psyco
        try:
            spell = None
            try:
                spell = self.gtkspell.get_from_text_view(text_view)
            except SystemError, e:
                # At least on Mandriva .get_from_text_view() sometimes returns
                # a SystemError without a description. Things seem to work fine
                # anyway, so let's ignore it and hope for the best.
                pass
            if spell is None:
                spell = self.gtkspell.Spell(text_view, language)
            else:
                spell.set_language(language)
                spell.recheck_all()
            text_view.spell_lang = language
        except Exception, e:
            logging.exception("Could not initialize spell checking", e)
            self.gtkspell = None
            #TODO: unload plugin
    if psyco:
        # Some of the gtkspell stuff can't work with psyco and will dump core
        # if we don't avoid psyco compilation
        psyco.cannotcompile(_activate_checker)

    def _on_populate_popup(self, textbox, menu):
        # We can't work with the menu immediately, since gtkspell only adds its
        # entries in the event handler.
        gobject.idle_add(self._fix_menu, menu)

    def _fix_menu(self, menu):
        _entries_above_separator = False
        _now_remove_separator = False
        for item in menu:
            if item.get_name() == 'GtkSeparatorMenuItem':
                if not _entries_above_separator:
                    menu.remove(item)
                break

            label = item.get_property('label')

            # For some reason the i18n of gtkspell doesn't work on Windows, so
            # we intervene.
            if label == "<i>(no suggestions)</i>":
                #l10n: This refers to spell checking
                item.set_property('label', _("<i>(no suggestions)</i>"))

            if label == "Ignore All":
                #l10n: This refers to spell checking
                item.set_property('label', _("Ignore All"))

            if label == "More...":
                #l10n: This refers to spelling suggestions
                item.set_property('label', _("More..."))

            m = _dict_add_re.match(label)
            if m:
                word = m.group(1)
                #l10n: This refers to the spell checking dictionary
                item.set_property('label', _('Add "%s" to Dictionary') % word)

            # We don't want a language selector - we have our own
            if label in dgettext('gtkspell', 'Languages'):
                menu.remove(item)
                if not _entries_above_separator:
                    _now_remove_separator = True
                    continue

            _entries_above_separator = True
