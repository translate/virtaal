#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2008 Zuza Software Foundation
#
# This file is part of virtaal.
#
# virtaal is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with translate; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import gobject

from translate.storage.poheader import poheader
from translate.storage import statsdb, factory
from translate.filters import checks
from translate.lang import factory as langfactory

import globals
from globals import _
from widgets.entry_dialog import EntryDialog
import modes

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

class Document(gobject.GObject):
    """Contains user state about a translate store which stores information like
    GUI-toolkit-independent state (for example bookmarks) and index remappings
    which are needed to"""

    __gtype_name__ = "Document"

    __gsignals__ = {
        "mode-changed": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
    }

    def compute_nplurals(self):
        nplurals = None
        if isinstance(self.store, poheader):
            header = self.store.parseheader()
            if 'Plural-Forms' in header:
                # XXX: BUG: Got files from GNOME with plurals but without this header
                nplurals, plural = self.store.getheaderplural()
                if nplurals is None:
                    langcode = globals.settings.language["contentlang"]
                    self._lang = langfactory.getlanguage(langcode)
                    nplurals = self._lang.nplurals
                    plural = self._lang.pluralequation
                    while not nplurals:
                        try:
                            entry = EntryDialog(_("Please enter the number of noun forms (plurals) to use"))
                            if entry is None:
                                return
                            nplurals = int(entry)
                        except ValueError, _e:
                            continue
                        plural = EntryDialog(_("Please enter the plural equation to use"))
                        globals.settings.language["nplurals"] = nplurals
                        globals.settings.language["plural"] = plural
                    self.store.updateheaderplural(nplurals, plural)
        return int(nplurals or 0)

    def __init__(self, filename, store=None):
        gobject.GObject.__init__(self)
        if store:
            self.store = store
        else:
            self.store = factory.getobject(filename)
        self.stats = statsdb.StatsCache().filestats(filename, checks.UnitChecker(), self.store)
        self._lang = None
        self.nplurals = self.compute_nplurals()
        self.mode = None
        self.mode_cursor = None

    def set_mode(self, name):
        print "Changing mode to %s" % name
        self.mode = modes.MODES[name](self.stats)
        try:
            if self.mode_cursor != None:
                self.mode_cursor = self.mode.cursor_from_element(self.mode_cursor.deref())
            else:
                self.mode_cursor = self.mode.cursor_from_element()

            if self.mode_cursor.get_pos() < 0:
                try:
                    self.mode_cursor.move(1)
                except IndexError:
                    pass

            self.emit('mode-changed', self.mode)
        except IndexError:
            pass

    def get_modes(self):
        # We isolate the rest of the program logic from the modes which
        # might be associated with a document. This allows us to supply
        # modes based on the document type.
        return modes.MODES.itervalues()

