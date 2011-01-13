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

import gtk

from virtaal.views.widgets.popupmenubutton import PopupMenuButton

from baseview import BaseView


class ChecksProjectView(BaseView):
    """Manages project type selection and other quality checks UI elements."""

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller
        self.current_project = None
        self._checker_menu_items = {}

        self._create_project_button()

    def _create_project_button(self):
        self.btn_proj = PopupMenuButton(label=_('Project Type'))
        menu = gtk.Menu()
        for checkercode in self.controller.checker_info:
            checkername = self.controller._checker_code_to_name[checkercode]
            mitem = gtk.MenuItem(checkername)
            mitem.show()
            mitem.connect('activate', self._on_menu_item_activate)
            menu.append(mitem)
            self._checker_menu_items[checkername] = mitem
        self.btn_proj.set_menu(menu)


    # METHODS #
    def show(self):
        statusbar = self.controller.main_controller.view.status_bar
        for child in statusbar.get_children():
            if child is self.btn_proj:
                return
        statusbar.pack_start(self.btn_proj, expand=False)
        statusbar.show_all()

    def set_checker_name(self, cname):
        # l10n: The label indicating the checker style (GNOME/KDE/whatever)
        self.btn_proj.set_label(_('Checks: %(checker_name)s') % {'checker_name': cname})


    # EVENT HANDLER #
    def _on_menu_item_activate(self, menuitem):
        self.controller.set_checker_by_name(menuitem.child.get_label())
