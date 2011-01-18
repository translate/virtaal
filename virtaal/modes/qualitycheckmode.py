#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2011 Zuza Software Foundation
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
        self.main_controller = controller.main_controller
        self._checker_set_id = None
        self.filter_checks = []
        # a way to map menuitems to their check names, and signal ids:
        self._menuitem_checks = {}
        self.store_filename = None


    # METHODS #
    def _prepare_stats(self):
        self.store_controller.update_store_checks(checker=self.main_controller.checks_controller.get_checker())
        self.stats = self.store_controller.get_store_checks()
        # A currently selected check might disappear if the style changes:
        self.filter_checks = [check for check in self.filter_checks if check in self.stats]
        self.storecursor = self.store_controller.cursor
        self.checks_names = {}
        for check, indices in self.stats.iteritems():
            if indices and check not in ('total', 'translated', 'untranslated', 'extended'):
                self.checks_names[check] = self.main_controller.checks_controller.get_check_name(check)

    def selected(self):
        self._prepare_stats()
        self._checker_set_id = self.main_controller.checks_controller.connect('checker-set', self._on_checker_set)
        # redo stats on save to refresh navigation controls
        self._store_saved_id = self.store_controller.connect('store-saved', self._on_checker_set)

        self._add_widgets()
        self._update_button_label()
        self.update_indices()

    def unselected(self):
        if self._checker_set_id:
            self.main_controller.checks_controller.disconnect(self._checker_set_id)
            self._checker_set_id = None
            self.store_controller.disconnect(self._store_saved_id)
            self.store_saved_id = None

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
        self._create_menu_entries(menu)
        return menu

    def _create_menu_entries(self, menu):
        for mi, (name, signal_id) in self._menuitem_checks.iteritems():
            mi.disconnect
            menu.remove(mi)
        assert not menu.get_children()
        for check_name, display_name in sorted(self.checks_names.iteritems(), key=lambda x: x[1], cmp=locale.strcoll):
            #l10n: %s is the name of the check and must be first. %d is the number of failures
            menuitem = gtk.CheckMenuItem(label="%s (%d)" % (display_name, len(self.stats[check_name])))
            menuitem.set_active(check_name in self.filter_checks)
            menuitem.show()
            self._menuitem_checks[menuitem] = (check_name, menuitem.connect('toggled', self._on_check_menuitem_toggled))
            menu.append(menuitem)

    def _update_button_label(self):
        check_labels = [mi.child.get_label() for mi in self.btn_popup.menu if mi.get_active()]
        btn_label = u''
        if not check_labels:
            #l10n: This is the button where the user can select units by failing quality checks
            btn_label = _(u'Select Checks')
        elif len(check_labels) == len(self.checks_names):
            #l10n: This refers to quality checks
            btn_label = _(u'All Checks')
        else:
            btn_label = u', '.join(check_labels[:3])
            if len(check_labels) > 3:
                btn_label += u'...'
        self.btn_popup.set_label(btn_label)


    # EVENT HANDLERS #
    def _on_checker_set(self, checkscontroller, checker=None):
        self._prepare_stats()
        self._create_menu_entries(self.btn_popup.menu)
        self._update_button_label()
        self.update_indices()

    def _on_check_menuitem_toggled(self, checkmenuitem):
        self.filter_checks = []
        for menuitem in self.btn_popup.menu:
            if not isinstance(menuitem, gtk.CheckMenuItem) or not menuitem.get_active():
                continue
            if menuitem in self._menuitem_checks:
                self.filter_checks.append(self._menuitem_checks[menuitem][0])
        self.update_indices()
        self._update_button_label()
