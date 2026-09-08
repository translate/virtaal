#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk
from gi.repository import GLib

from virtaal.views.widgets.popupmenubutton import PopupMenuButton, POS_NW_SW
from .basemode import BaseMode


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
        # Destroy the previous popup button and its menu now rather
        # than just dropping the references - see
        # PopupMenuButton.set_menu()'s own comment for why relying on
        # Python's cyclic GC to eventually collect them isn't safe
        # here. destroy()ing the button doesn't reach the menu itself
        # (it's attached via GTK's popup mechanism, not as a normal
        # child), so both need doing explicitly.
        if hasattr(self, 'btn_popup'):
            self.btn_popup.menu.destroy()
            self.btn_popup.destroy()
            # destroy() above already tore down the old menuitems -
            # forget them, rather than leaking their now-dead widget
            # references in this dict forever.
            self._menuitem_states = {}

        table = self.controller.view.mode_box
        self.btn_popup = PopupMenuButton(menu_pos=POS_NW_SW)
        self.btn_popup.set_relief(Gtk.ReliefStyle.NORMAL)
        self.btn_popup.set_menu(self._create_state_menu())

        self.widgets = [self.btn_popup]

        xoptions = Gtk.AttachOptions.FILL
        table.attach(self.btn_popup, 2, 3, 0, 1, xoptions=xoptions)

        table.show_all()

    def _create_state_menu(self):
        menu = Gtk.Menu()

        for iid, name in self.state_names:
            menuitem = Gtk.CheckMenuItem(label=name)
            menuitem.show()
            self._menuitem_states[menuitem] = iid
            menuitem.connect('toggled', self._on_state_menuitem_toggled)
            menu.append(menuitem)
        return menu

    def _update_button_label(self):
        state_labels = [mi.get_child().get_label() for mi in self.btn_popup.menu if mi.get_active()]
        btn_label = ''
        if not state_labels:
            #l10n: This is the button where the user can select units by workflow state
            btn_label = _('Select States')
        elif len(state_labels) == len(self.state_names):
            #l10n: This refers to workflow states
            btn_label = _('All States')
        else:
            btn_label = ', '.join(state_labels[:3])
            if len(state_labels) > 3:
                btn_label += '...'
        self.btn_popup.set_label(btn_label)

    def _disable(self):
        """Disable the widgets (workflow not possible now)."""
        self.btn_popup.set_sensitive(False)

    # EVENT HANDLERS #
    def _on_state_menuitem_toggled(self, checkmenuitem):
        # update_indices() rebuilds the treeview; deferred to idle_add
        # so that doesn't happen while the popup's own grab is still
        # held (a plausible segfault source - see the commit message).
        self.filter_states = []
        for menuitem in self.btn_popup.menu:
            if not isinstance(menuitem, Gtk.CheckMenuItem) or not menuitem.get_active():
                continue
            if menuitem in self._menuitem_states:
                self.filter_states.append(self._menuitem_states[menuitem])
        GLib.idle_add(self._apply_filter_states)
        self._update_button_label()

    def _apply_filter_states(self):
        self.update_indices()
        return False
