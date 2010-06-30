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

from virtaal.views.widgets.popupwidgetbutton import PopupWidgetButton

from baseview import BaseView


class ChecksUnitView(BaseView):
    """The unit specific view for quality checks."""

    COL_CHECKNAME, COL_DESC = range(2)

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller

        self.vbox_popup = self._create_popup_vbox()
        self._create_checks_button(self.vbox_popup)
        self._create_menu_item()

    def _create_checks_button(self, widget):
        self.btn_checks = PopupWidgetButton(widget, label=_('No issues'))
        self.btn_checks.connect('shown', self._on_popup_shown)

    def _create_menu_item(self):
        mainview = self.controller.main_controller.view
        mainview.gui.get_widget('mnu_checks').connect('activate', self._on_activated)

    def _create_popup_vbox(self):
        vb = gtk.VBox()

        self.lbl_empty = gtk.Label('<i>' + _('No issues') + '</i>')
        self.lbl_empty.set_use_markup(True)
        self.lbl_empty.hide()
        vb.pack_start(self.lbl_empty)

        self.lst_checks = gtk.ListStore(str, str)
        self.tvw_checks = gtk.TreeView()
        self.tvw_checks.append_column(
            gtk.TreeViewColumn(_('Quality Check'), gtk.CellRendererText(), text=self.COL_CHECKNAME)
        )
        self.tvw_checks.append_column(
            gtk.TreeViewColumn(_('Description'), gtk.CellRendererText(), text=self.COL_DESC)
        )
        self.tvw_checks.set_model(self.lst_checks)

        self.scw_checks = gtk.ScrolledWindow()
        self.scw_checks.add(self.tvw_checks)
        vb.pack_start(self.scw_checks)

        return vb


    # METHODS #
    def show(self):
        parent = self.controller.main_controller.unit_controller.view._widgets['vbox_right']
        parent.pack_start(self.btn_checks, expand=False, fill=True)
        self.btn_checks.show()


    # EVENT HANDLERS #
    def _on_activated(self, menu_iitem):
        self.btn_checks.clicked()

    def _on_popup_shown(self, button):
        pass
