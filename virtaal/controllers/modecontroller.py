#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GLib, GObject

from virtaal.common import GObjectWrapper

from .basecontroller import BaseController


class ModeController(BaseController):
    """
    Contains logic for switching and managing unit selection modes.

    In the context of modes, models always represent a specific mode. So it's
    not strictly a data model (as it contains its own logic), but it is the
    standard type of object that is manipulated and handled by this controller
    and C{ModeView} objects.
    """

    __gtype_name__ = 'ModeController'
    __gsignals__ = {
        'mode-selected': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        # After the shown units have changed for the new context.
        'context-selected': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }
    default_mode_name = 'Default'

    # INITIALIZERS #
    def __init__(self, main_controller):
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.main_controller.mode_controller = self

        self._init_modes()
        from virtaal.views.modeview import ModeView
        self.view = ModeView(self)
        self.view.connect('mode-selected', self._on_mode_selected)
        self._mode_list_just_closed = False
        self.view.cmb_modes.connect('notify::popup-shown', self._on_mode_list_shown)
        from virtaal.views.storeview import load_context_setting
        self.view.select_context(load_context_setting())
        self.view.connect('context-selected', self._on_context_selected)

        self.current_mode = None
        self.view.select_mode(self.modenames[self.default_mode_name])

        store_controller = self.main_controller.store_controller
        store_controller.connect('store-loaded', self._on_store_changed)
        store_controller.connect('stats-changed', self._on_store_changed)
        store_controller.connect('store-closed', self._on_store_closed)

    def _init_modes(self):
        self.modes = {}
        self.modenames = {}

        from virtaal.modes import modeclasses
        for modeclass in modeclasses:
            newmode = modeclass(self)
            self.modes[newmode.name] = newmode
            self.modenames[newmode.name] = newmode.display_name


    # ACCESSORS #
    def get_mode_by_display_name(self, displayname):
        candidates = [mode for name, mode in self.modes.items() if mode.display_name == displayname]
        if candidates:
            return candidates[0]


    # METHODS #
    def refresh_mode(self):
        if not self.current_mode:
            self.select_default_mode()
        else:
            self.select_mode(self.current_mode)

    def update_mode_availability(self):
        self.view.set_unavailable_modes(
            [mode.display_name for mode in self.modes.values() if not mode.is_available()]
        )

    def select_default_mode(self):
        self.select_mode_by_name(self.default_mode_name)

    def select_mode_by_display_name(self, displayname):
        self.select_mode(self.get_mode_by_display_name(displayname))

    def select_mode_by_name(self, name):
        self.select_mode(self.modes[name])

    def select_mode(self, mode):
        if not mode.is_available():
            # E.g. reapplying Incomplete to a newly opened file with nothing
            # incomplete.
            mode = self.modes[self.default_mode_name]
        if self.current_mode:
            self.view.remove_mode_widgets(self.current_mode.widgets)
            self.current_mode.unselected()

        self.current_mode = mode
        self._ignore_mode_change = True
        self.view.select_mode(self.modenames[mode.name])
        self._ignore_mode_change = False
        self.view.show()
        # Every unit is shown in the default mode, so context doesn't apply.
        self.view.set_context_sensitive(mode.name != self.default_mode_name)
        self.current_mode.selected()
        import logging
        logging.info('Mode selected: %s' % (self.current_mode.name))
        self.emit('mode-selected', self.current_mode)

    # EVENT HANDLERS #
    def _on_mode_selected(self, _modeview, modename):
        if not getattr(self, '_ignore_mode_change', True):
            self.select_mode(self.get_mode_by_display_name(modename))
            # A choice from the open list, not arrowing through the closed
            # selector: carry on to what that mode needs next.
            if self._mode_list_just_closed:
                self._mode_list_just_closed = False
                GLib.idle_add(self._continue_after_choosing_mode)

    def _on_mode_list_shown(self, combo, _pspec):
        if combo.props.popup_shown:
            return
        # A choice from the list is reported right after it closes.
        self._mode_list_just_closed = True

        def unchanged():
            # Choosing the current mode again, or Escape: no change is
            # reported, but the selector is done with all the same.
            if self._mode_list_just_closed:
                self._mode_list_just_closed = False
                self._continue_after_choosing_mode()
            return GLib.SOURCE_REMOVE
        GLib.idle_add(unchanged)

    def _continue_after_choosing_mode(self):
        """Open the mode's own menu if it has one, then go to the unit being
            translated; focus left on the selector would take keys like
            Alt+Down (#1925). Search focuses its own entry."""
        mode = self.current_mode
        button = getattr(mode, 'btn_popup', None)
        if button is not None and button.get_sensitive():
            def on_menu_closed(menu):
                menu.disconnect(handler_id)
                GLib.idle_add(self._focus_translation)
            handler_id = button.menu.connect('deactivate', on_menu_closed)
            button.set_active(True)
        elif not mode.widgets:
            self._focus_translation()
        return GLib.SOURCE_REMOVE

    def _focus_translation(self):
        unit_view = self.main_controller.unit_controller.view
        targets = getattr(unit_view, 'targets', None)
        if self.main_controller.store_controller.get_store() is not None and targets:
            targets[unit_view.focused_target_n or 0].grab_focus()
        return GLib.SOURCE_REMOVE

    def _on_context_selected(self, _modeview, context):
        self.main_controller.store_controller.view.set_context(context)
        self.emit('context-selected', context)

    def _on_store_changed(self, _store_controller):
        self.update_mode_availability()

    def _on_store_closed(self, store_controller):
        self.view.set_unavailable_modes([])
        self.select_default_mode()
        self.view.hide()
