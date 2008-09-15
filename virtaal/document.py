#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
#
# This file is part of VirTaal.
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

import gobject

from translate.storage.poheader import poheader
from translate.storage import statsdb, factory
from translate.filters import checks
from translate.lang import factory as langfactory

import pan_app
from widgets.entry_dialog import EntryDialog
from mode_selector import ModeSelector

def get_document(obj):
    """See whether obj contains an attribute called 'document'.
    If it does, return the attribute value. Otherwise, see if
    it has a parent (via the attribute 'parent') and ask the
    parent if it contains 'document'. If there is no parent
    and no 'document' attribute, return None."""
    if not hasattr(obj, 'document'):
        if hasattr(obj, 'parent'):
            return get_document(getattr(obj, 'parent'))
        else:
            return None
    else:
        return getattr(obj, 'document')

def compute_nplurals(store):
    def ask_for_language_details():
        def get_content_lang():
            if pan_app.settings.language["contentlang"] != None:
                return pan_app.settings.language["contentlang"]
            else:
                return EntryDialog(_("Please enter the language code for the target language"))

        def ask_for_number_of_plurals():
            while True:
                try:
                    entry = EntryDialog(_("Please enter the number of noun forms (plurals) to use"))
                    return int(entry)
                except ValueError, _e:
                    pass
                  
        def ask_for_plurals_equation():
            return EntryDialog(_("Please enter the number of noun forms (plurals) to use"))

        lang     = langfactory.getlanguage(get_content_lang())
        nplurals = lang.nplurals or ask_for_number_of_plurals()
        if nplurals > 1 and lang.pluralequation == "0":
            return nplurals, ask_for_plurals_equation()
        else:
            return nplurals, lang.pluralequation
    
    if isinstance(store, poheader):
        nplurals, _pluralequation = store.getheaderplural()
        if nplurals is None:
            nplurals, pluralequation = ask_for_language_details()
            pan_app.settings.language["nplurals"] = nplurals
            pan_app.settings.language["plural"]   = pluralequation
            store.updateheaderplural(nplurals, pluralequation)
        return int(nplurals)
    else:
        return 1

class Document(gobject.GObject):
    """Contains user state about a translate store which stores information like
    GUI-toolkit-independent state (for example bookmarks) and index remappings
    which are needed to"""

    __gtype_name__ = "Document"

    __gsignals__ = {
        "cursor-changed": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
        "mode-changed": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
    }

    def __init__(self, filename, store=None, mode_selector=None):
        gobject.GObject.__init__(self)
        if store:
            self.store = store
        else:
            self.store = factory.getobject(filename)
        if mode_selector is None:
            mode_selector = ModeSelector(self)
        self.stats = statsdb.StatsCache().filestats(filename, checks.UnitChecker(), self.store)
        self.nplurals = compute_nplurals(self.store)
        self.mode = None
        self.mode_cursor = None
        self.mode_selector = mode_selector

        self.set_mode(self.mode_selector.default_mode)
        self.mode_selector.connect('mode-combo-changed', self._on_mode_combo_changed)

    def refresh_cursor(self):
        try:
            old_cursor = self.mode_cursor
            if self.mode_cursor != None:
                self.mode_cursor = self.mode.cursor_from_element(self.mode_cursor.deref())
            else:
                self.mode_cursor = self.mode.cursor_from_element()

            if self.mode_cursor.get_pos() < 0:
                try:
                    self.mode_cursor.move(1)
                except IndexError:
                    pass
            if old_cursor != self.mode_cursor:
                self.emit('cursor-changed')
            return True
        except IndexError:
            return False

    def set_mode(self, mode):
        logging.debug("Changing document mode to %s" % mode.mode_name)

        self.mode_selector.set_mode(mode)
        self.mode = mode

        if self.refresh_cursor():
            self.emit('mode-changed', mode)

    def _on_mode_combo_changed(self, _mode_selector, mode):
        self.set_mode(mode)
