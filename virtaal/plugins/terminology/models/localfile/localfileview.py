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


class LocalFileView:
    """
    Class that manages the localfile terminology plug-in's GUI presense and interaction.
    """

    # INITIALIZERS #
    def __init__(self, model):
        self.term_model = model
        self.controller = model.controller
        self.mainview = model.controller.main_controller.view
        self._signal_ids = []
        self._setup_menus()


    # METHODS #
    def _setup_menus(self):
        self.mnu_term = self.mainview.find_menu(_('_Terminology'))
        self.mnu_select_files, _menu = self.mainview.find_menu_item(_('Terminology _files...'), self.mnu_term)
        if not self.mnu_select_files:
            self.mnu_select_files = self.mainview.append_menu_item(_('Terminology _files...'), self.mnu_term)
        self._signal_ids.append((
            self.mnu_select_files,
            self.mnu_select_files.connect('activate', self._on_select_term_files)
        ))

    def destroy(self):
        for gobj, signal_id in self._signal_ids:
            gobj.disconnect(signal_id)

        menuitem, menu = self.mainview.find_menu_item(_('Terminology _files...'), self.mnu_term)
        if menuitem and menu:
            assert menu is self.mnu_term
            assert menuitem is self.mnu_select_files
            menu.get_submenu().remove(menuitem)


    # EVENT HANDLERS #
    def _on_select_term_files(self, menuitem):
        dlg = gtk.FileChooserDialog(
            _('Select file(s) to use for terminology...'),
            self.controller.main_controller.view.main_window,
            gtk.FILE_CHOOSER_ACTION_OPEN,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK)
        )
        dlg.set_select_multiple(True)
        dlg.show_all()
        response = dlg.run()
        dlg.hide()

        if response != gtk.RESPONSE_OK:
            return

        self.term_model.config['files'] = dlg.get_filenames()
