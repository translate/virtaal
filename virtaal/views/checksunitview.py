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
from translate.lang import factory as lang_factory

from virtaal.common.pan_app import get_ui_lang
from virtaal.views.widgets.popupwidgetbutton import PopupWidgetButton, POS_SE_NE

from baseview import BaseView


class ChecksUnitView(BaseView):
    """The unit specific view for quality checks."""

    COL_CHECKNAME, COL_DESC = range(2)

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller
        main_controller = controller.main_controller

        self.popup_content = self._create_popup_content()
        self._create_checks_button(self.popup_content)
        self._create_menu_item()
        main_controller.store_controller.connect('store-closed', self._on_store_closed)

        self._listsep = lang_factory.getlanguage(get_ui_lang()).listseperator
        self._prev_failures = None

    def _create_checks_button(self, widget):
        import pango
        self.lbl_btnchecks = gtk.Label(_('No issues'))
        self.lbl_btnchecks.show()
        self.lbl_btnchecks.set_ellipsize(pango.ELLIPSIZE_END)
        self.btn_checks = PopupWidgetButton(widget, label=None, popup_pos=POS_SE_NE)
        self.btn_checks.set_update_popup_geometry_func(self.update_geometry)
        self.btn_checks.add(self.lbl_btnchecks)

    def _create_menu_item(self):
        mainview = self.controller.main_controller.view
        mainview.gui.get_widget('mnu_checks').connect('activate', self._on_activated)

    def _create_popup_content(self):
        vb = gtk.VBox()
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        frame.add(vb)

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

        vb.pack_start(self.tvw_checks)

        return frame


    # METHODS #
    def show(self):
        parent = self.controller.main_controller.unit_controller.view._widgets['vbox_right']
        parent.pack_start(self.btn_checks, expand=False, fill=True)
        self.btn_checks.show()

    def hide(self):
        if self.btn_checks.get_active():
            self.btn_checks.clicked()

    def update(self, failures):
        self._prev_failures = failures
        if not failures:
            self.lbl_btnchecks.set_text(_('No issues'))
            self._show_empty_label()
            return

        self.lst_checks.clear()
        names = []
        for testname, desc in failures.iteritems():
            testname = self.controller.get_check_name(testname)
            self.lst_checks.append([testname, desc])
            names.append(testname)

        self.lbl_btnchecks.set_text(self._listsep.join(names))
        self._show_treeview()

    def _show_empty_label(self):
        self.tvw_checks.hide()
        self.lbl_empty.show()

    def _show_treeview(self):
        self.lbl_empty.hide()
        self.tvw_checks.show_all()

    def update_geometry(self, popup, popup_alloc, btn_alloc, btn_window_xy, geom):
        x, y, width, height = geom

        textbox = self.controller.main_controller.unit_controller.view.sources[0]
        alloc = textbox.get_allocation()

        if width > alloc.width:
            return x, y, alloc.width, height
        return geom


    # EVENT HANDLERS #
    def _on_activated(self, menu_iitem):
        self.btn_checks.clicked()

    def _on_store_closed(self, store_controller):
        self.hide()
