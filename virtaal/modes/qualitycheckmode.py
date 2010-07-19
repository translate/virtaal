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

from virtaal.views.widgets.popupmenubutton import PopupMenuButton, POS_NW_SW

from basemode import BaseMode


class QualityCheckMode(BaseMode):
    """Include units based on quality checks that units fail."""

    name = 'QualityCheck'
    display_name = _("Quality Checks")
    widgets = []

    # INITIALIZERS #
    def __init__(self, controller):
        """Constructor.
            @type  controller: virtaal.controllers.ModeController
            @param controller: The ModeController that managing program modes."""
        self.controller = controller
        self.store_controller = controller.main_controller.store_controller
        self.checks_controller = controller.main_controller.checks_controller
        self._checker_set_id = None
        self.filter_checks = []
        self._menuitem_checks = {}
        self.store_filename = None


    # METHODS #
    def selected(self):
        self.stats = self.store_controller.get_store_stats()
        self.storecursor = self.store_controller.cursor
        self.checks_names = {}
        for check, indices in self.stats.iteritems():
            if indices and check not in ('total', 'translated', 'untranslated'):
                self.checks_names[check] = self.checks_controller.get_check_name(check)

        self._checker_set_id = self.checks_controller.connect(
            'checker-set', self._on_checker_set
        )

        self._add_widgets()
        self._update_button_label()
        self.update_indices()

    def unselected(self):
        if self._checker_set_id:
            self.checks_controller.disconnect(self._checker_set_id)
            self._checker_set_id = None

    def update_indices(self):
        if not self.storecursor or not self.storecursor.model:
            return

        indices = []
        for check in self.filter_checks:
            indices.extend(self.stats[check])

        if not indices:
            indices = range(len(self.storecursor.model))
        indices.sort()

        self.storecursor.indices = indices

    def _add_widgets(self):
        table = self.controller.view.mode_box
        self.btn_popup = PopupMenuButton(menu_pos=POS_NW_SW)
        self.btn_popup.set_relief(gtk.RELIEF_NORMAL)
        self.btn_popup.set_menu(self._create_checks_menu())

        self.widgets = [self.btn_popup]

        xoptions = gtk.FILL
        table.attach(self.btn_popup, 2, 3, 0, 1, xoptions=xoptions)

        table.show_all()

    def _create_checks_menu(self):
        menu = gtk.Menu()

        for check_name, display_name in self.checks_names.iteritems():
            menuitem = gtk.CheckMenuItem(label=display_name)
            menuitem.show()
            self._menuitem_checks[menuitem] = check_name
            menuitem.connect('toggled', self._on_check_menuitem_toggled)
            menu.append(menuitem)
        return menu

    def _update_button_label(self):
        check_labels = [mi.child.get_label() for mi in self.btn_popup.menu if mi.get_active()]
        btn_label = u''
        if not check_labels:
            btn_label = _(u'No Checks')
        elif len(check_labels) == len(self.checks_names):
            btn_label = _(u'All Checks')
        else:
            btn_label = u', '.join(check_labels[:3])
            if len(check_labels) > 3:
                btn_label += u'...'
        self.btn_popup.set_label(btn_label)


    # EVENT HANDLERS #
    def _on_checker_set(self, checkscontroller, checker):
        self.unselected()
        self.selected()

    def _on_check_menuitem_toggled(self, checkmenuitem):
        self.filter_checks = []
        for menuitem in self.btn_popup.menu:
            if not isinstance(menuitem, gtk.CheckMenuItem) or not menuitem.get_active():
                continue
            if menuitem in self._menuitem_checks:
                self.filter_checks.append(self._menuitem_checks[menuitem])
        self.update_indices()
        self._update_button_label()
