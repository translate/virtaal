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

import gtk
import logging

from translate.tools.pogrep import GrepFilter


class SearchMode(UnionSetEnumerator):
    mode_name = "Search"
    user_name = _("Search")
    widgets = []

    def __init__(self):
        UnionSetEnumerator.__init__(self)
        self.ent_search = gtk.Entry()
        self.ent_search.connect('changed', self._on_search_text_changed)
        self.chk_casesensitive = gtk.CheckButton(_('Case sensitive'))
        self.chk_regex = gtk.CheckButton(_("Regex matching"))

        self.widgets = [self.ent_search, self.chk_casesensitive, self.chk_regex]

    def refresh(self, document):
        self.document = document
        if not self.ent_search.get_text():
            UnionSetEnumerator.__init__(self, SortedSet(document.stats['total']))
        else:
            self._on_search_text_changed(self.ent_search)

    def _on_search_text_changed(self, entry):
        search_text = entry.get_text()
        logging.debug('Search text: %s' % (search_text))

        # Filter stats with text in "entry"
        filtered = []
        i = 0
        for unit in self.document.store.units:
            if search_text in unit.source or search_text in unit.target:
                filtered.append(i)
            i += 1

        UnionSetEnumerator.__init__(self, SortedSet(filtered))
