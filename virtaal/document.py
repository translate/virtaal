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

from translate.storage.poheader import poheader
from translate.lang import factory as langfactory

import Globals
from EntryDialog import EntryDialog

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

class Document(object):
    """Contains user state about a translate store which stores information like
    GUI-toolkit-independent state (for example bookmarks) and index remappings
    which are needed to """
    
    def compute_nplurals(self):
        nplurals = None
        if isinstance(self.store, poheader):
            header = self.store.parseheader()
            if 'Plural-Forms' in header:
                # XXX: BUG: Got files from GNOME with plurals but without this header
                nplurals, plural = self.store.getheaderplural()
                if nplurals is None:
                    langcode = Globals.settings.language["contentlang"]
                    self._lang = langfactory.getlanguage(langcode)
                    nplurals = self._lang.nplurals
                    plural = self._lang.pluralequation
                    while not nplurals:
                        try:
                            entry = EntryDialog("Please enter the number of noun forms (plurals) to use")
                            if entry is None:
                                return
                            nplurals = int(entry)
                        except ValueError, _e:
                            continue
                        plural = EntryDialog("Please enter the plural equation to use")
                        Globals.settings.language["nplurals"] = nplurals
                        Globals.settings.language["plural"] = plural
                    self.store.updateheaderplural(nplurals, plural)
        return int(nplurals or 0)
    
    def __init__(self, store):
        self.store = store
        self._lang = None
        self.nplurals = self.compute_nplurals()
        self.unit_index_remap = [i for i, unit in enumerate(self.store.units) if unit.istranslatable()]

    def get_translatable_units(self):
        def yield_units():
            for i in self.unit_index_remap:
                yield self.store.units[i]
        return yield_units()
        
    