#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010 Zuza Software Foundation
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

import os
from virtaal.common import pan_app
from virtaal.controllers import BasePlugin

class Plugin(BasePlugin):
    """A plugin to control spell checking.

    It can also download spell checkers on Windows."""

    display_name = _('Spell Checker')
    description = _('Check spelling and provide suggestions')
    version = 0.1

    # INITIALIZERS #
    def __init__(self, internal_name, main_controller):
        self.internal_name = internal_name

        # If these imports fail, the plugin is automatically disabled
        import gtkspell
        import enchant
        self.gtkspell = gtkspell
        self.enchant = enchant

        self.unit_view = main_controller.unit_controller.view
        self._connect_id = self.unit_view.connect('textview-language-changed', self._on_unit_lang_changed)

    def destroy(self):
        """Remove signal connections and disable spell checking."""
        if getattr(self, '_connect_id', None):
            self.unit_view.disconnect(self._connect_id)
        for text_view in self.unit_view.sources + self.unit_view.targets:
            self._disable_checking(text_view)

    # METHODS #
    def _disable_checking(self, text_view):
        """Disable checking on the given text_view."""
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


    # SIGNAL HANDLERS #
    def _on_unit_lang_changed(self, unit_view, text_view, language):
        if not self.gtkspell:
            return

        if not self.enchant.dict_exists(language):
            # Sometimes enchants *wants* a country code, other times it does not.
            # For the cases where it requires one, we look for the first language
            # code that enchant supports and use that one.
            if len(language) > 4:
                #logging.debug('len("%s") > 4' % (language))
                return

            for code in self.enchant.list_languages():
                if code.startswith(language):
                    language = code
                    break
            else:
                #logging.debug('No code in enchant.list_languages() that starts with "%s"' % (language))

                # We couldn't find a dictionary for "language", so we should make sure that we don't
                # have a spell checker for a different language on the text view. See bug 717.
                self._disable_checking(text_view)
                return

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

    if not pan_app.DEBUG:
        try:
            import psyco
            psyco.cannotcompile(_on_unit_lang_changed)
        except ImportError, e:
            pass
