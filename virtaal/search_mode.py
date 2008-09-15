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

import gobject
import gtk
import logging

from translate.tools.pogrep import GrepFilter

from virtaal.support.set_enumerator import UnionSetEnumerator
from virtaal.support.sorted_set import SortedSet


class SearchMode(UnionSetEnumerator):
    mode_name = "Search"
    user_name = _("Search")
    widgets = []

    def __init__(self):
        UnionSetEnumerator.__init__(self)
        self.ent_search = gtk.Entry()
        self.ent_search.connect('changed', self._on_search_text_changed)
        self.default_base = gtk.widget_get_default_style().base[gtk.STATE_NORMAL]
        self.default_text = gtk.widget_get_default_style().text[gtk.STATE_NORMAL]
        self.chk_casesensitive = gtk.CheckButton(_('Case sensitive'))
        self.chk_casesensitive.connect('toggled', self._refresh_proxy)
        self.chk_regex = gtk.CheckButton(_("Regex matching"))
        self.chk_regex.connect('toggled', self._refresh_proxy)

        self.widgets = [self.ent_search, self.chk_casesensitive, self.chk_regex]

        self.makefilter()

    def makefilter(self):
        searchstring = self.ent_search.get_text()
        searchparts = ('source', 'target')
        ignorecase = not self.chk_casesensitive.get_active()
        useregexp = self.chk_regex.get_active()

        self.filter = GrepFilter(searchstring, searchparts, ignorecase, useregexp)

    def refresh(self, document):
        self.document = document
        if not self.ent_search.get_text():
            UnionSetEnumerator.__init__(self, SortedSet(document.stats['total']))
        else:
            self._on_search_text_changed(self.ent_search)

    def handle_unit(self, editor):
        """Highlights all occurances of the search string in the newly selected unit."""
        if self.chk_regex.get_active():
            return

    def selected(self):
        """Focus the search entry.

            This method should only be called after this mode has been selected."""
        def grab_focus():
            self.ent_search.grab_focus()
            return False

        # FIXME: The following line is a VERY UGLY HACK, but at least it works.
        gobject.timeout_add(100, grab_focus)

    def _on_search_text_changed(self, entry):
        self.makefilter()

        # Filter stats with text in "entry"
        filtered = []
        i = 0
        for unit in self.document.store.units:
            if self.filter.filterunit(unit):
                filtered.append(i)
            i += 1

        logging.debug('Search text: %s (%d matches)' % (entry.get_text(), len(filtered)))

        if filtered:
            self.ent_search.modify_base(gtk.STATE_NORMAL, self.default_base)
            self.ent_search.modify_text(gtk.STATE_NORMAL, self.default_text)
        else:
            self.ent_search.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse('#f66'))
            self.ent_search.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('#fff'))

        UnionSetEnumerator.__init__(self, SortedSet(filtered))

    def _refresh_proxy(self, *args):
        self._on_search_text_changed(self.ent_search)
