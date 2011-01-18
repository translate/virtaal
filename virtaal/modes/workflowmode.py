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

import logging
import gtk

from virtaal.views.widgets.popupmenubutton import PopupMenuButton, POS_NW_SW

from basemode import BaseMode


class WorkflowMode(BaseMode):
    """Workflow mode - Include units based on its workflow state, as specified
        by the user."""

    name = 'Workflow'
    display_name = _("Workflow")
    widgets = []

    # INITIALIZERS #
    def __init__(self, controller):
        """Constructor.
            @type  controller: virtaal.controllers.ModeController
            @param controller: The ModeController that managing program modes."""
        self.controller = controller
        self.filter_states = []
        self._menuitem_states = {}


    # METHODS #
    def selected(self):
        self.storecursor = self.controller.main_controller.store_controller.cursor

        self.state_names = self.controller.main_controller.unit_controller.get_unit_state_names()
        if self.storecursor and self.storecursor.model and 'extended' in self.storecursor.model.stats:
            self.state_names = [i for i in self.state_names.items() if i[0] in self.storecursor.model.stats['extended']]
        else:
            self.state_names = self.state_names.items()

        self.state_names.sort(key=lambda x: x[0])

        self._add_widgets()
        self._update_button_label()
        if not self.state_names:
            self._disable()
        self.update_indices()

    def unselected(self):
        pass

    def update_indices(self):
        if not self.storecursor or not self.storecursor.model:
            return

        indices = []
        for state in self.filter_states:
            indices.extend(self.storecursor.model.stats['extended'][state])

        if not indices:
            indices.extend(self.storecursor.model.stats['total'])
        else:
            indices.sort()

        self.storecursor.indices = indices

    def _add_widgets(self):
        table = self.controller.view.mode_box
        self.btn_popup = PopupMenuButton(menu_pos=POS_NW_SW)
        self.btn_popup.set_relief(gtk.RELIEF_NORMAL)
        self.btn_popup.set_menu(self._create_state_menu())

        self.widgets = [self.btn_popup]

        xoptions = gtk.FILL
        table.attach(self.btn_popup, 2, 3, 0, 1, xoptions=xoptions)

        table.show_all()

    def _create_state_menu(self):
        menu = gtk.Menu()

        for iid, name in self.state_names:
            menuitem = gtk.CheckMenuItem(label=name)
            menuitem.show()
            self._menuitem_states[menuitem] = iid
            menuitem.connect('toggled', self._on_state_menuitem_toggled)
            menu.append(menuitem)
        return menu

    def _update_button_label(self):
        state_labels = [mi.child.get_label() for mi in self.btn_popup.menu if mi.get_active()]
        btn_label = u''
        if not state_labels:
            #l10n: This is the button where the user can select units by workflow state
            btn_label = _(u'Select States')
        elif len(state_labels) == len(self.state_names):
            #l10n: This refers to workflow states
            btn_label = _(u'All States')
        else:
            btn_label = u', '.join(state_labels[:3])
            if len(state_labels) > 3:
                btn_label += u'...'
        self.btn_popup.set_label(btn_label)

    def _disable(self):
        """Disable the widgets (workflow not possible now)."""
        self.btn_popup.set_sensitive(False)

    # EVENT HANDLERS #
    def _on_state_menuitem_toggled(self, checkmenuitem):
        self.filter_states = []
        for menuitem in self.btn_popup.menu:
            if not isinstance(menuitem, gtk.CheckMenuItem) or not menuitem.get_active():
                continue
            if menuitem in self._menuitem_states:
                self.filter_states.append(self._menuitem_states[menuitem])
        self.update_indices()
        self._update_button_label()
