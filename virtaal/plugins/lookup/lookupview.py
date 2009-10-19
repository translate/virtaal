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

from virtaal.views import BaseView


class LookupView(BaseView):
    """
    Makes look-up models accessible via the source- and target text views'
    context menu.
    """

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller
        self.lang_controller = controller.main_controller.lang_controller

        self._connect_to_unitview(controller.main_controller.unit_controller.view)

    def _connect_to_unitview(self, unitview):
        self._textbox_ids = []
        for textbox in unitview.sources + unitview.targets:
            self._textbox_ids.append((
                textbox,
                textbox.connect('populate-popup', self._on_populate_popup)
            ))


    # METHODS #
    def destroy(self):
        for textbox, id in self._textbox_ids:
            textbox.disconnect(id)


    # SIGNAL HANDLERS #
    def _on_lookup_selected(self, menuitem, plugin, query, query_is_source):

        plugin.lookup(query, query_is_source, srclang, tgtlang)

    def _on_populate_popup(self, textbox, menu):
        buf = textbox.buffer
        if not buf.get_has_selection():
            return

        selection = buf.get_text(*buf.get_selection_bounds())
        role      = textbox.role
        srclang   = self.lang_controller.source_lang.code
        tgtlang   = self.lang_controller.target_lang.code

        lookup_menu = gtk.Menu()
        menu_item = gtk.MenuItem(_('Look-up "%(selection)s"') % {'selection': selection})

        plugins = self.controller.plugin_controller.plugins
        menu_items = []
        names = plugins.keys()
        names.sort()
        for name in names:
            menu_items.extend(
                plugins[name].create_menu_items(selection, role, srclang, tgtlang)
            )
        for i in menu_items:
            lookup_menu.append(i)

        sep = gtk.SeparatorMenuItem()
        sep.show()
        menu.append(sep)
        menu_item.set_submenu(lookup_menu)
        menu_item.show_all()
        menu.append(menu_item)
