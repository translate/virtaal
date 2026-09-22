#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging

from gi.repository import Gdk, GLib, GObject, Gtk

from virtaal.common import GObjectWrapper, SignalTracker
from virtaal.views.baseview import BaseView

from .tmwidgets import TMWindow


class TMView(BaseView, GObjectWrapper):
    """The fake drop-down menu in which the TM matches are displayed."""

    __gtype_name__ = 'TMView'
    __gsignals__ = {
        'tm-match-selected': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    # INITIALIZERS #
    def __init__(self, controller, max_matches):
        GObjectWrapper.__init__(self)

        self.controller = controller
        self.isvisible = False
        self.max_matches = max_matches
        self._may_show_tmwindow = True # is it allowed to display now (application is in focus)
        self._should_show_tmwindow = False # should it be displayed now (even if it doesn't, due to application focus?
        self._signal_tracker = SignalTracker()

        self.tmwindow = TMWindow(self)
        main_window = self.controller.main_controller.view.main_window

        self._signal_tracker.connect(self.tmwindow.treeview, 'row-activated', self._on_row_activated)
        self._signal_tracker.connect(
            controller.main_controller.store_controller.view.parent_widget.get_vscrollbar(),
            'value-changed', self._on_store_view_scroll)
        self._signal_tracker.connect(main_window, 'grab-notify', self._on_grab_notify_mainwindow)
        self._signal_tracker.connect(main_window, 'configure_event', self._on_configure_mainwindow)
        self._signal_tracker.connect(controller.main_controller.store_controller, 'store-closed', self._on_store_closed)
        self._signal_tracker.connect(controller.main_controller.store_controller, 'store-loaded', self._on_store_loaded)

        self._setup_key_bindings()
        self._setup_menu_items()

    def _setup_key_bindings(self):
        """Setup Gtk+ key bindings (accelerators)."""

        Gtk.AccelMap.add_entry("<Virtaal>/TM/Hide TM", Gdk.KEY_Escape, 0)

        self.accel_group = Gtk.AccelGroup()
        self.accel_group.connect_by_path("<Virtaal>/TM/Hide TM", self._on_hide_tm)

        # Connect Ctrl+n (1 <= n <= 9) to select match n.
        for i in range(1, 10):
            numstr = str(i)
            numkey = Gdk.KEY_0 + i
            Gtk.AccelMap.add_entry("<Virtaal>/TM/Select match " + numstr, numkey, Gdk.ModifierType.CONTROL_MASK)
            self.accel_group.connect_by_path("<Virtaal>/TM/Select match " + numstr, self._on_select_match)

        mainview = self.controller.main_controller.view
        mainview.add_accel_group(self.accel_group)

    def _setup_menu_items(self):
        mainview = self.controller.main_controller.view
        menubar = mainview.menubar
        self.mnui_view = mainview.gui.get_object('menuitem_view')
        self.menu = self.mnui_view.get_submenu()

        self.mnu_suggestions = Gtk.CheckMenuItem.new_with_mnemonic(label=_('Translation _Suggestions'))
        self.mnu_suggestions.show()
        self.menu.append(self.mnu_suggestions)

        Gtk.AccelMap.add_entry("<Virtaal>/TM/Toggle Show TM", Gdk.KEY_F9, 0)
        accel_group = self.menu.get_accel_group()
        if accel_group is None:
            accel_group = self.accel_group
            self.menu.set_accel_group(self.accel_group)
        self.mnu_suggestions.set_accel_path("<Virtaal>/TM/Toggle Show TM")
        self.menu.set_accel_group(accel_group)

        self.mnu_suggestions.connect('toggled', self._on_toggle_show_tm)
        self.mnu_suggestions.set_active(True)


    # ACCESSORS #
    def _get_active(self):
        return self.mnu_suggestions.get_active()
    active = property(_get_active)


    # METHODS #
    def clear(self):
        """Clear the TM matches."""
        self.tmwindow.liststore.clear()
        self.hide()

    def destroy(self):
        self._signal_tracker.disconnect_all()

        self.menu.remove(self.mnu_suggestions)

    def display_matches(self, matches):
        """Add the list of TM matches to those available and show the TM window."""
        liststore = self.tmwindow.liststore
        liststore.clear()
        for match in matches:
            tooltip = ''
            if len(liststore) < 9:
                tooltip = _('Ctrl+%(number_key)d') % {"number_key": len(liststore)+1}
            liststore.append([match, tooltip])

        if len(liststore) > 0:
            self.show()
            self.update_geometry()

    def get_target_width(self):
        if not hasattr(self.controller, 'unit_view'):
            return -1
        n = self.controller.unit_view.focused_target_n
        textview = self.controller.unit_view.targets[n]
        return textview.get_allocation().width

    def hide(self):
        """Hide the TM window."""
        self.tmwindow.hide()
        self.isvisible = False

    def select_backends(self, parent):
        from virtaal.views.backendselect import select_backends
        select_backends(
            self.controller.main_controller, self.controller.plugin_controller,
            self.controller.config, 'basetmmodel',
            #l10n: The 'sources' here refer to different translation memory plugins,
            #such as local tm, open-tran.eu, the current file, etc.
            title=_('Select sources of Translation Memory'),
            message=_('Select the sources that should be queried for translation memory'),
            size=(550, 580),
            parent=parent,
        )

    def select_match(self, match_data):
        """Select the match data as accepted by the user."""
        self.controller.select_match(match_data)

    def select_match_index(self, index):
        """Select the TM match with the given index (first match is 1).
            This method causes a row in the TM window's C{Gtk.TreeView} to be
            selected and activated. This runs this class's C{_on_select_match()}
            method which runs C{select_match()}."""
        if index < 0 or not self.isvisible:
            return

        logging.debug('Selecting index %d' % (index))
        liststore = self.tmwindow.liststore
        itr = liststore.get_iter_first()

        i=1
        while itr and i < index and liststore.iter_is_valid(itr):
            itr = liststore.iter_next(itr)
            i += 1

        if not itr or not liststore.iter_is_valid(itr):
            return

        path = liststore.get_path(itr)
        self.tmwindow.treeview.get_selection().select_iter(itr)
        self.tmwindow.treeview.row_activated(path, self.tmwindow.tvc_match)

    def show(self, force=False):
        """Show the TM window."""
        if not self.active or (self.isvisible and not force) or not self._may_show_tmwindow:
            return # This window is already visible
        self.tmwindow.show_all()
        self.isvisible = True
        self._should_show_tmwindow = False

    def update_geometry(self):
        """Update the TM window's position and size."""
        def update():
            selected = self._get_selected_unit_view()
            if selected:
                self.tmwindow.update_geometry(selected)

        GLib.idle_add(update)

    def _get_selected_unit_view(self):
        n = self.controller.main_controller.unit_controller.view.focused_target_n
        if n is None:
            # There is no unit. Nothing to do.
            return None
        return self.controller.main_controller.unit_controller.view.targets[n]


    # EVENT HANDLERS #
    def _on_grab_notify_mainwindow(self, widget, was_grabbed):
        # focus-in/out-event used to drive this, but a same-app modal
        # dialog (e.g. Preferences) never triggers those on the main
        # window - it stays "focused" the whole time, so the popup was
        # never hidden and drew over the dialog. grab-notify fires when
        # the window is actually shadowed by another widget's grab,
        # which is what a running Gtk.Dialog does.
        if was_grabbed:
            self._may_show_tmwindow = True
            if not self._should_show_tmwindow or self.isvisible:
                return
            if not self.controller.storecursor:
                return # No store loaded
            self.show()

            selected = self._get_selected_unit_view()
            self.tmwindow.update_geometry(selected)
        else:
            if isinstance(Gtk.grab_get_current(), Gtk.Menu):
                # A plain popup menu (e.g. the Workflow/Quality-Check mode
                # buttons) also takes an implicit grab when it opens, same
                # as a modal dialog. Treating that as "a modal dialog
                # opened" and hiding this window fights with the menu's
                # own grab and can dismiss the menu prematurely (#3689).
                # Only an actual modal window should hide the TM window.
                return
            self._may_show_tmwindow = False
            if not self.isvisible:
                return
            self.hide()
            self._should_show_tmwindow = True

    def _on_configure_mainwindow(self, widget, event):
        if self._should_show_tmwindow:
            # For some reason tvc_tm_source needs this help to recalculate its
            # size, otherwise it goes through the roof (rhs of the screen), and
            # the size calculation of the renderer isn't even called. See bug
            # 1809.
            self.tmwindow.tvc_tm_source.queue_resize()
            self.update_geometry()

    def _on_hide_tm(self, accel_group, acceleratable, keyval, modifier):
        self.hide()

    def _on_row_activated(self, treeview, path, column):
        """Called when a TM match is selected in the TM window."""
        liststore = treeview.get_model()
        assert liststore is self.tmwindow.liststore
        itr = liststore.get_iter(path)
        match_data = liststore.get_value(itr, 0)

        self.select_match(match_data)

    def _on_select_match(self, accel_group, acceleratable, keyval, modifier):
        self.select_match_index(int(keyval - Gdk.KEY_0))

    def _on_store_closed(self, storecontroller):
        self.hide()
        self.mnu_suggestions.set_sensitive(False)

    def _on_store_loaded(self, storecontroller):
        self.mnu_suggestions.set_sensitive(True)

    def _on_store_view_scroll(self, *args):
        if self.isvisible:
            self.hide()

    def _on_toggle_show_tm(self, *args):
        if not self.active and self.isvisible:
            self.hide()
        elif self.active and not self.isvisible:
            self.controller.start_query()
