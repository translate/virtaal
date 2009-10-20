#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 Zuza Software Foundation
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

import gtk
import urllib

from baselookupmodel import BaseLookupModel


class LookupModel(BaseLookupModel):
    """Look-up the selected string on the web."""

    __gtype_name__ = 'WebLookupModel'
    display_name = _('Web Look-up')
    description = _('Use the selected text as the query string in a web look-ups.')

    URLS = (
        (
            _('Google'),
            'http://www.google.com/search?q=%(query)s',
            {'quoted': True}
        ),
    )

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.controller = controller
        self.internal_name = internal_name


    # METHODS #
    def create_menu_items(self, query, role, srclang, tgtlang):
        query = urllib.quote(query)
        items = []
        for name, url, options in self.URLS:
            uquery = query
            if 'quoted' in options and options['quoted']:
                uquery = '"' + uquery + '"'

            i = gtk.MenuItem(name)
            lookup_str = url % {
                'query':   query,
                'role':    role,
                'srclang': srclang,
                'tgtlang': tgtlang
            }
            i.connect('activate', self._on_lookup, lookup_str)
            items.append(i)
        return items


    # SIGNAL HANDLERS #
    def _on_lookup(self, menuitem, url):
        from virtaal.support.openmailto import open
        open(url)
