#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GObject, Gtk

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
        # The number of units to show around the one being edited, or None for all.
        "context-selected": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    # INITIALIZERS #
    def __init__(self, controller):
        GObjectWrapper.__init__(self)

        self.controller = controller
        self._unavailable = set()
        self._build_gui()
        self._load_modes()

    def _build_gui(self):
        # Get the mode container from the main controller
        # We need the *same* GtkBuilder instance as used by the MainView, because we need
        # the Gtk.Grid as already added to the main window. Loading the GtkBuilder file again
        # would create a new main window with a different Gtk.Grid.
        gui = self.controller.main_controller.view.gui # FIXME: Is this acceptable?
        self.mode_box = gui.get_object('mode_box')

        self.cmb_modes = Gtk.ComboBoxText()
        # Any wrap width opens the menu below the combo box, instead of
        # over it lined up with the active mode.
        self.cmb_modes.set_wrap_width(1)
        self.cmb_modes.connect('changed', self._on_cmbmode_change)
        self.cmb_modes.set_cell_data_func(self.cmb_modes.get_cells()[0], self._set_cell_sensitive)

        self.lbl_mode = Gtk.Label()
        #l10n: This refers to the 'mode' that determines how Virtaal moves
        #between units.
        self.lbl_mode.set_markup_with_mnemonic(_('N_avigation:'))
        self.lbl_mode.props.xpad = 3
        self.lbl_mode.set_mnemonic_widget(self.cmb_modes)
        # The mnemonic opens the list, so a keyboard choice is made from it.
        self.cmb_modes.connect('mnemonic-activate', self._on_cmbmode_mnemonic)
        self.lbl_mode.set_halign(Gtk.Align.CENTER)
        self.lbl_mode.set_valign(Gtk.Align.CENTER)
        self.cmb_modes.set_halign(Gtk.Align.CENTER)
        self.cmb_modes.set_valign(Gtk.Align.CENTER)

        self.mode_box.attach(self.lbl_mode, 0, 0, 1, 1)
        self.mode_box.attach(self.cmb_modes, 1, 0, 1, 1)

        self._build_context_gui(gui.get_object('hbox1'))

    def _build_context_gui(self, top_bar):
        self.cmb_context = Gtk.ComboBoxText()
        self.cmb_context.set_wrap_width(1)
        #l10n: Context: show no units around the one being edited
        self.cmb_context.append('0', _('None'))
        for count in ('1', '2', '3'):
            self.cmb_context.append(count, count)
        #l10n: Context: show every unit, not only the matching ones
        self.cmb_context.append('all', _('All'))
        self.cmb_context.connect('changed', self._on_cmbcontext_change)

        lbl_context = Gtk.Label()
        #l10n: How many units to show around the one being edited, when a
        #navigation mode only goes to some units
        lbl_context.set_markup_with_mnemonic(_('Conte_xt:'))
        lbl_context.set_mnemonic_widget(self.cmb_context)

        self.context_box = Gtk.Box(spacing=3)
        self.context_box.pack_start(lbl_context, False, False, 0)
        self.context_box.pack_start(self.cmb_context, False, False, 0)
        self.context_box.set_valign(Gtk.Align.CENTER)
        self.context_box.set_margin_end(6)
        top_bar.pack_end(self.context_box, False, False, 0)

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
        self.context_box.hide()

    def remove_mode_widgets(self, widgets):
        if not widgets:
            return

        # Remove previous mode's widgets
        if self.cmb_modes.get_active() > -1:
            for w in self.mode_box.get_children():
                if w in widgets:
                    self.mode_box.remove(w)

    def set_unavailable_modes(self, displaynames):
        """Grey out the given modes in the mode selector."""
        self._unavailable = set(displaynames)
        model = self.cmb_modes.get_model()
        # row_changed() makes the popup re-read each row's sensitivity.
        for row in model:
            model.row_changed(row.path, row.iter)

    def select_mode(self, displayname):
        if displayname in self.displayname_index:
            self.cmb_modes.set_active(self.displayname_index[displayname])
        else:
            raise ValueError('Unknown mode specified: %s' % (displayname))

    def show(self):
        self.mode_box.show_all()
        self.context_box.show_all()

    def select_context(self, context):
        """Show C{context} (a number of units, or None for all) as selected,
            without emitting "context-selected"."""
        self._ignore_context_change = True
        self.cmb_context.set_active_id('all' if context is None else str(context))
        self._ignore_context_change = False

    def set_context_sensitive(self, sensitive):
        self.context_box.set_sensitive(sensitive)

    def focus(self):
        """Open the mode list, so a keyboard choice is made from it."""
        self.cmb_modes.grab_focus()
        self.cmb_modes.popup()

    def _set_cell_sensitive(self, _layout, cell, model, iter_, _data=None):
        cell.set_property('sensitive', model[iter_][0] not in self._unavailable)

    # EVENT HANDLERS #
    def _on_cmbcontext_change(self, combo):
        if getattr(self, '_ignore_context_change', False):
            return
        active = combo.get_active_id()
        self.emit('context-selected', None if active == 'all' else int(active))

    def _on_cmbmode_mnemonic(self, _combo, _group_cycling):
        self.focus()
        return True

    def _on_cmbmode_change(self, combo):
        self.emit('mode-selected', combo.get_active_text())
