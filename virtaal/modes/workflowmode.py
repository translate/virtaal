#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GLib, Gtk

from virtaal.views.widgets.popupmenubutton import POS_NW_SW, PopupMenuButton

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
        self._stats_changed_id = None


    # METHODS #
    def selected(self):
        store_controller = self.controller.main_controller.store_controller
        self.storecursor = store_controller.cursor
        if not self._stats_changed_id:
            self._stats_changed_id = store_controller.connect('stats-changed', self._on_stats_changed)
        self.state_names = self._format_state_names()
        # Selecting the mode starts a new selection: drop ticked states
        # that no unit is in.
        self.filter_states = [state for state in self.filter_states if self._has_units(state)]

        self._add_widgets()
        self._update_button_label()
        if not self.state_names:
            self._disable()
        self.update_indices()

    def unselected(self):
        if self._stats_changed_id:
            self.controller.main_controller.store_controller.disconnect(self._stats_changed_id)
            self._stats_changed_id = None

    def update_indices(self):
        if not self.storecursor or not self.storecursor.model:
            return

        if not self.filter_states:
            # No state selected is no filter: include every unit.
            self.storecursor.indices = self.storecursor.model.stats['total']
            return

        indices = []
        for state in self.filter_states:
            indices.extend(self.storecursor.model.stats['extended'].get(state, []))
        self.storecursor.indices = sorted(indices)

    def _format_state_names(self):
        """The (id, name) pairs of the workflow states the file's format has,
            or of the states its units are in if the format has none."""
        names = self.controller.main_controller.unit_controller.get_unit_state_names()
        model = self.storecursor.model if self.storecursor else None
        if not model:
            return sorted(names.items())
        states = []
        if len(model):
            # Negative states (obsolete) aren't workflow states.
            states = [state for state, (low, _high) in type(model[0]).STATE.items() if low >= 0]
        if not states:
            states = list(model.stats.get('extended', {}))
        return sorted((state, names[state]) for state in states if state in names)

    def _has_units(self, state):
        model = self.storecursor.model if self.storecursor else None
        return bool(model and model.stats.get('extended', {}).get(state))

    def _update_menu_sensitivity(self):
        """Only states with units can be ticked; a ticked one stays
            sensitive so it can be unticked."""
        for menuitem, state in self._menuitem_states.items():
            menuitem.set_sensitive(self._has_units(state) or menuitem.get_active())

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

        self.btn_popup.set_vexpand(True)
        table.attach(self.btn_popup, 2, 0, 1, 1)

        table.show_all()

    def _create_state_menu(self):
        menu = Gtk.Menu()

        for iid, name in self.state_names:
            menuitem = Gtk.CheckMenuItem(label=name)
            menuitem.set_active(iid in self.filter_states)
            menuitem.set_sensitive(self._has_units(iid) or iid in self.filter_states)
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
        self._update_menu_sensitivity()

    def _on_stats_changed(self, _store_controller):
        # The units under review stay until the selection changes.
        self._update_menu_sensitivity()

    def _apply_filter_states(self):
        self.update_indices()
        return False
