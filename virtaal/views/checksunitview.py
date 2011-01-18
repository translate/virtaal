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

import locale

import gtk
import pango
from translate.lang import factory as lang_factory

from virtaal.common.pan_app import ui_language
from virtaal.views.widgets.popupwidgetbutton import PopupWidgetButton, POS_SE_NE

from baseview import BaseView


class ChecksUnitView(BaseView):
    """The unit specific view for quality checks."""

    COL_CHECKNAME, COL_DESC = range(2)

    # INITIALIZERS #
    def __init__(self, controller):
        self.controller = controller
        main_controller = controller.main_controller
        main_window = main_controller.view.main_window

        self.popup_content = self._create_popup_content()
        self._create_checks_button(self.popup_content, main_window)
        self._create_menu_item()
        main_controller.store_controller.connect('store-closed', self._on_store_closed)
        main_controller.store_controller.connect('store-loaded', self._on_store_loaded)

        self._prev_failures = None
        self._listsep = lang_factory.getlanguage(ui_language).listseperator

    def _create_checks_button(self, widget, main_window):
        self.lbl_btnchecks = gtk.Label()
        self.lbl_btnchecks.show()
        self.lbl_btnchecks.set_ellipsize(pango.ELLIPSIZE_END)
        self.btn_checks = PopupWidgetButton(widget, label=None, popup_pos=POS_SE_NE, main_window=main_window, sticky=True)
        self.btn_checks.set_property('relief', gtk.RELIEF_NONE)
        self.btn_checks.set_update_popup_geometry_func(self.update_geometry)
        self.btn_checks.add(self.lbl_btnchecks)

    def _create_menu_item(self):
        mainview = self.controller.main_controller.view
        self.mnu_checks = mainview.gui.get_widget('mnu_checks')
        self.mnu_checks.connect('activate', self._on_activated)

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
        name_column = gtk.TreeViewColumn(_('Quality Check'), gtk.CellRendererText(), text=self.COL_CHECKNAME)
        name_column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self.tvw_checks.append_column(name_column)

        description_renderer = gtk.CellRendererText()
        #description_renderer.set_property('wrap-mode', pango.WRAP_WORD_CHAR)
        description_column = gtk.TreeViewColumn(_('Description'), description_renderer, text=self.COL_DESC)
        description_column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self.tvw_checks.append_column(description_column)
        self.tvw_checks.set_model(self.lst_checks)
        self.tvw_checks.get_selection().set_mode(gtk.SELECTION_NONE)

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
        # We don't want to show "untranslated"
        failures.pop('untranslated', None)
        if failures == self._prev_failures:
            return
        self._prev_failures = failures
        if not failures:
            # We want an empty button, but this causes a bug where subsequent
            # updates don't show, so we set it to a non-breaking space
            self.lbl_btnchecks.set_text(u"\u202a")
            self._show_empty_label()
            self.btn_checks.set_tooltip_text(u"")
            return

        self.lst_checks.clear()
        nice_name = self.controller.get_check_name
        sorted_failures = sorted(failures.iteritems(), key=lambda x: nice_name(x[0]), cmp=locale.strcoll)
        names = []
        for testname, desc in sorted_failures:
            testname = nice_name(testname)
            self.lst_checks.append([testname, desc])
            names.append(testname)

        name_str = self._listsep.join(names)
        self.btn_checks.set_tooltip_text(name_str)
        self.lbl_btnchecks.set_text(name_str)
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

        if width > alloc.width * 1.3:
            return x, y, int(alloc.width * 1.3), height
        return geom


    # EVENT HANDLERS #
    def _on_activated(self, menu_iitem):
        self.btn_checks.clicked()

    def _on_store_closed(self, store_controller):
        self.mnu_checks.set_sensitive(False)
        self.hide()

    def _on_store_loaded(self, store_controller):
        self.mnu_checks.set_sensitive(True)
