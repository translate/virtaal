#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GObject
from gi.repository import Gtk

from virtaal.common import GObjectWrapper
from .baseview import BaseView


class ModeView(GObjectWrapper, BaseView):
    """
    Manages the mode selection on the GUI and communicates with its associated
    C{ModeController}.
    """

    __gtype_name__ = 'ModeView'
    __gsignals__ = {
        "mode-selected": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_STRING,)),
    }

    # INITIALIZERS #
    def __init__(self, controller):
        GObjectWrapper.__init__(self)

        self.controller = controller
        self._build_gui()
        self._load_modes()

    def _build_gui(self):
        # Get the mode container from the main controller
        # We need the *same* GtkBuilder instance as used by the MainView, because we need
        # the Gtk.Table as already added to the main window. Loading the GtkBuilder file again
        # would create a new main window with a different Gtk.Table.
        gui = self.controller.main_controller.view.gui # FIXME: Is this acceptable?
        self.mode_box = gui.get_object('mode_box')

        self.cmb_modes = Gtk.ComboBoxText()
        self.cmb_modes.connect('changed', self._on_cmbmode_change)

        self.lbl_mode = Gtk.Label()
        #l10n: This refers to the 'mode' that determines how Virtaal moves
        #between units.
        self.lbl_mode.set_markup_with_mnemonic(_('N_avigation:'))
        self.lbl_mode.props.xpad = 3
        self.lbl_mode.set_mnemonic_widget(self.cmb_modes)

        self.mode_box.attach(self.lbl_mode, 0, 1, 0, 1, xoptions=0, yoptions=0)
        self.mode_box.attach(self.cmb_modes, 1, 2, 0, 1, xoptions=0, yoptions=0)

    def _load_modes(self):
        self.displayname_index = {}
        i = 0
        for name in self.controller.modes:
            displayname = self.controller.modenames[name]
            self.cmb_modes.append_text(displayname)
            self.displayname_index[displayname] = i
            i += 1


    # METHODS #
    def hide(self):
        self.mode_box.hide()

    def remove_mode_widgets(self, widgets):
        if not widgets:
            return

        # Remove previous mode's widgets
        if self.cmb_modes.get_active() > -1:
            for w in self.mode_box.get_children():
                if w in widgets:
                    self.mode_box.remove(w)

    def select_mode(self, displayname):
        if displayname in self.displayname_index:
            self.cmb_modes.set_active(self.displayname_index[displayname])
        else:
            raise ValueError('Unknown mode specified: %s' % (displayname))

    def show(self):
        self.mode_box.show_all()

    def focus(self):
        self.cmb_modes.grab_focus()

    # EVENT HANDLERS #
    def _on_cmbmode_change(self, combo):
        self.emit('mode-selected', combo.get_active_text())
