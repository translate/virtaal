#!/usr/bin/env python
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

from gi.repository import GLib

from virtaal.common.platform import platform
from virtaal.controllers.baseplugin import PluginUnsupported, BasePlugin


_dict_add_re = re.compile('Add "(.*)" to Dictionary')


class Plugin(BasePlugin):
    """A plugin to control spell checking."""

    display_name = _('Spell Checker')
    description = _('Check spelling and provide suggestions')
    version = 0.1

    # INITIALIZERS #
    def __init__(self, internal_name, main_controller):
        self.internal_name = internal_name

        if platform.is_frozen:
            # No version-matched gtkspell3 bundled yet (UI-stage work) -
            # a frozen build must never trust a system-found one: a
            # mismatched GTK3 copy crashes outright (GTK_IS_TEXT_VIEW
            # assertion, ObjC duplicate-class registration) rather than
            # just failing to import.
            raise PluginUnsupported("gtkspell3 isn't bundled in a frozen build")

        if platform.is_windows:
            DICTDIR = os.path.join(os.environ['APPDATA'], 'enchant', 'myspell')
            # DICTDIR is already str (unicode text) under Python 3, so there's
            # nothing to decode - .decode() doesn't exist on str at all and
            # raised AttributeError unconditionally here. The original intent
            # (enchant won't work on Windows with a non-ascii path) still
            # applies though, so check encodability instead of decoding.
            try:
                DICTDIR.encode('ascii')
            except UnicodeEncodeError:
                raise PluginUnsupported("Spell checking is not supported with non-ascii username")

        # If these imports fail, the plugin is automatically disabled -
        # gi.require_version() raises ValueError (not ImportError) when
        # the typelib itself is simply missing (true for this project's
        # gvsbuild GTK3 build, which doesn't ship GtkSpell/enchant at
        # all), so both need catching here, not just ImportError.
        try:
            import gi
            gi.require_version('GtkSpell', '3.0')
            from gi.repository import GtkSpell as gtkspell
            import enchant
        except (ImportError, ValueError) as e:
            raise PluginUnsupported(str(e))
        self.gtkspell = gtkspell
        self.enchant = enchant
        # languages that we've handled before:
        self._seen_languages = {}
        # languages supported by enchant:
        self._enchant_languages = self.enchant.list_languages()

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

    def _disable_checking(self, text_view):
        """Disable checking on the given text_view."""
        if getattr(text_view, 'spell_lang', 'xxxx') is None:
            # No change necessary - already disabled
            return
        spell = None
        try:
            spell = self.gtkspell.Checker.get_from_text_view(text_view)
        except SystemError as e:
            # At least on Mandriva .get_from_text_view() sometimes returns
            # a SystemError without a description. Things seem to work fine
            # anyway, so let's ignore it and hope for the best.
            raise e
            pass
        if not spell is None:
            spell.detach()
        text_view.spell_lang = None


    # SIGNAL HANDLERS #
    def _on_unit_lang_changed(self, unit_view, text_view, language):
        if not self.gtkspell:
            return

        # enchant doesn't like anything except plain strings (bug 1852)
        language = str(language)

        if language == 'en':
            language = 'en_US'
        elif language == 'pt':
            language = 'pt_PT'
        elif language == 'de':
            language = 'de_DE'

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
                # DictionaryDownloadWatcher (wired to LanguageController,
                # not this per-textview signal) handles trying to
                # download a missing dictionary - nothing to do here but
                # degrade gracefully for now.

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
        GLib.idle_add(self._activate_checker, text_view, language, priority=GLib.PRIORITY_LOW)

    def _activate_checker(self, text_view, language):
        # All the expensive stuff in here called on idle.
        try:
            spell = None
            try:
                spell = self.gtkspell.Checker.get_from_text_view(text_view)
            except SystemError as e:
                # At least on Mandriva .get_from_text_view() sometimes returns
                # a SystemError without a description. Things seem to work fine
                # anyway, so let's ignore it and hope for the best.
                pass
            if spell is None:
                spell = self.gtkspell.Checker()
                spell.attach(text_view)
            spell.set_language(language)
            spell.recheck_all()
            text_view.spell_lang = language
        except Exception as e:
            logging.exception("Could not initialize spell checking: %s", e)
            self.gtkspell = None
            #TODO: unload plugin

    def _on_populate_popup(self, textbox, menu):
        # We can't work with the menu immediately, since gtkspell only adds its
        # entries in the event handler.
        GLib.idle_add(self._fix_menu, menu)

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
