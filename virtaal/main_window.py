#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
#
# This file is part of VirTaal.
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

import os
import os.path as path
import time

try:
    import pygtk
    pygtk.require("2.0")
except:
    pass

import gobject
import gtk
from gtk import gdk
from gtk import glade

from translate.storage import poheader
from support import openmailto

import pan_app
from pan_app import _ # _() is the gettext function to use
from widgets.entry_dialog import EntryDialog
import unit_grid
import unit_renderer
from about import About
import formats
import document
from support import bijection

# FIXME: Add docstrings!

def on_undo(_accel_group, acceleratable, _keyval, _modifier):
    unit_renderer.undo(acceleratable.focus_widget)

class ModeBox(gtk.HBox):
    __gtype_name__ = "ModeBox"

    __gsignals__ = {
        "mode-selected": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
    }

    def __init__(self, modes):
        gtk.HBox.__init__(self)

        def make_label(text):
            label_box = gtk.EventBox()
            label = gtk.Label()
            label.set_text(text)
            label_box.add(label)
            return label_box

        self.mode_to_label = bijection.Bijection((mode, make_label(mode.user_name)) for mode in modes)

        for label in self.mode_to_label.itervalues():
            self.pack_start(label)
            label.connect('button-release-event', self._on_label_click)

    def set_mode(self, mode):
        for label in self.get_children():
            label.child.set_label(self.mode_to_label.inverse[label].user_name)

        self.mode_to_label[mode].child.set_markup('<b>%s</b>' % self.mode_to_label[mode].child.get_text())

    def _on_label_click(self, clicked_label, _event):
        self.emit('mode-selected', self.mode_to_label.inverse[clicked_label])

def load_glade_file(filename):
    import sys

    BASE_DIRS = [
        os.path.dirname(unicode(__file__, sys.getfilesystemencoding())),
        os.path.dirname(unicode(sys.executable, sys.getfilesystemencoding()))
    ]

    GLADE_DIRS = [
        ["..", "share", "virtaal"],
        ["share", "virtaal"]
    ]

    for basepath, glade_dir in ((x, y) for x in BASE_DIRS for y in GLADE_DIRS):
        dir_and_filename = glade_dir + [filename]
        gladefile = path.join(basepath or path.dirname(__file__), *dir_and_filename)
        if path.exists(gladefile):
            gui = glade.XML(gladefile)
            return gladefile, gui
    raise Exception("Could not find %s" % (filename,))

class VirTaal:
    """The entry point class for VirTaal"""

    def __init__(self, startup_file=None):
        #Set the Glade file
        self.gladefile, self.gui = load_glade_file("virtaal.glade")

        #Create our events dictionary and connect it
        dic = {
                "on_mainwindow_destroy" : gtk.main_quit,
                "on_mainwindow_delete" : self._on_mainwindow_delete,
                "on_open_activate" : self._on_file_open,
                "on_save_activate" : self._on_file_save,
                "on_saveas_activate" : self._on_file_saveas,
                "on_about_activate" : self._on_help_about,
                "on_localization_guide_activate" : self._on_localization_guide,
                "on_menuitem_documentation_activate" : self._on_documentation,
                "on_menuitem_report_bug_activate" : self._on_report_bug,
                }
        self.gui.signal_autoconnect(dic)

        self.status_box = self.gui.get_widget("status_box")
        self.sw = self.gui.get_widget("scrolledwindow1")
        self.main_window = self.gui.get_widget("MainWindow")
        self._setup_key_bindings()
        self.main_window.show()

        self.modified = False
        self.filename = None

        self.unit_grid = None
        self.document = None
        if startup_file != None:
            self.load_file(startup_file)

    def _setup_key_bindings(self):
        self.accel_group = gtk.AccelGroup()
        self.main_window.add_accel_group(self.accel_group)
        gtk.accel_map_add_entry("<VirTaal>/Edit/Undo", gtk.keysyms.z, gdk.CONTROL_MASK)
        gtk.accel_map_add_entry("<VirTaal>/Navigation/Up", gtk.accelerator_parse("Up")[0], gdk.CONTROL_MASK)
        gtk.accel_map_add_entry("<VirTaal>/Navigation/Down", gtk.accelerator_parse("Down")[0], gdk.CONTROL_MASK)
        self.accel_group.connect_by_path("<VirTaal>/Edit/Undo", self._on_undo)

    def _on_undo(self, _accel_group, acceleratable, _keyval, _modifier):
        unit_renderer.undo(acceleratable.focus_widget)

    def _on_mainwindow_delete(self, _widget, _event):
        if self._confirm_unsaved(self.main_window):
            return True
        return False

    def _on_file_open(self, _widget, destroyCallback=None):
        chooser = formats.file_open_chooser(destroyCallback)
        chooser.set_transient_for(self.main_window)
        while True:
            response = chooser.run()
            if response == gtk.RESPONSE_OK:
                filename = chooser.get_filename()
                pan_app.settings.general["lastdir"] = path.dirname(filename)
                pan_app.settings.write()
                if self.open_file(filename, chooser):
                    break
            elif response == gtk.RESPONSE_CANCEL or \
                    response == gtk.RESPONSE_DELETE_EVENT:
                break
        chooser.destroy()

    def _confirm_unsaved(self, dialog):
        if self.modified:
            dialog = gtk.MessageDialog(dialog,
                            gtk.DIALOG_MODAL,
                            gtk.MESSAGE_QUESTION,
                            gtk.BUTTONS_YES_NO,
                            _("The current file was modified, but is not yet saved. Do you want to save it now?"))
            dialog.set_default_response(gtk.RESPONSE_YES)
            response = dialog.run()
            dialog.destroy()
            if response in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
                return True
            elif response == gtk.RESPONSE_YES:
                if self._on_file_save():
                    return True

    def open_file(self, filename, dialog, reload=False):
        if self._confirm_unsaved(dialog):
            return True
        if filename == self.filename and not reload:
            dialog = gtk.MessageDialog(dialog,
                            gtk.DIALOG_MODAL,
                            gtk.MESSAGE_QUESTION,
                            gtk.BUTTONS_YES_NO,
                            _("You selected the currently open file for opening. Do you want to reload the file?"))
            dialog.set_default_response(gtk.RESPONSE_NO)
            response = dialog.run()
            dialog.destroy()
            if response in [gtk.RESPONSE_NO, gtk.RESPONSE_DELETE_EVENT]:
                return True
        return self.load_file(filename, dialog=dialog)

    def _on_gui_mode_change(self, _mode_box, mode):
        self.document.set_mode(mode.mode_name)

    def _on_mode_change(self, _document, mode):
        self.mode_box.set_mode(mode.__class__)

    def load_file(self, filename, dialog=None, store=None):
        """Do the actual loading of the file into the GUI"""
        try:
            self.document = document.Document(filename, store=store)
            self.document.connect('mode-changed', self._on_mode_change)
            child = self.status_box.get_children()[0]
            self.status_box.remove(child)
            child.destroy()
            self.mode_box = ModeBox(self.document.get_modes())
            self.status_box.pack_start(self.mode_box)
            self.status_box.reorder_child(self.mode_box, 0)
            self.mode_box.connect('mode-selected', self._on_gui_mode_change)
            self.document.set_mode('Default')

            self.filename = filename
            self.unit_grid = unit_grid.UnitGrid(self)
            self.unit_grid.connect("modified", self._on_modified)
            child = self.sw.get_child()
            self.sw.remove(child)
            child.destroy()
            self.sw.add(self.unit_grid)
            self.main_window.connect("configure-event", self.unit_grid.on_configure_event)
            self.main_window.show_all()
            self.unit_grid.grab_focus()
            self._set_saveable(False)
            menuitem = self.gui.get_widget("saveas_menuitem")
            menuitem.set_sensitive(True)
            self.document.set_mode('Default')
        except IOError, e:
            dialog = gtk.MessageDialog(dialog or self.main_window,
                            gtk.DIALOG_MODAL,
                            gtk.MESSAGE_ERROR,
                            gtk.BUTTONS_OK,
                            (str(e)))
            dialog.run()
            dialog.destroy()
            return False
        return True

    def _set_saveable(self, value):
        menuitem = self.gui.get_widget("save_menuitem")
        menuitem.set_sensitive(value)
        if self.filename:
            modified = ""
            if value:
                modified = "*"
            self.main_window.set_title((_('VirTaal - %(current_file)s %(modified_marker)s') % {"current_file": path.basename(self.filename), "modified_marker": modified}).rstrip())
        self.modified = value

    def _on_modified(self, _widget):
        if not self.modified:
            self._set_saveable(True)

    def _on_file_save(self, _widget=None, filename=None):
        if isinstance(self.document.store, poheader.poheader):
            name = pan_app.settings.translator["name"]
            email = pan_app.settings.translator["email"]
            team = pan_app.settings.translator["team"]
            if not name:
                name = EntryDialog(_("Please enter your name"))
                if name is None:
                    # User cancelled
                    return True
                pan_app.settings.translator["name"] = name
            if not email:
                email = EntryDialog(_("Please enter your e-mail address"))
                if email is None:
                    # User cancelled
                    return True
                pan_app.settings.translator["email"] = email
            if not team:
                team = EntryDialog(_("Please enter your team's information"))
                if team is None:
                    # User cancelled
                    return True
                pan_app.settings.translator["team"] = team
            pan_app.settings.write()
            po_revision_date = time.strftime("%F %H:%M%z")
            header_updates = {}
            header_updates["PO_Revision_Date"] = po_revision_date
            header_updates["X_Generator"] = pan_app.x_generator
            if name or email:
                header_updates["Last_Translator"] = u"%s <%s>" % (name, email)
                self.document.store.updatecontributor(name, email)
            if team:
                header_updates["Language-Team"] = team
            self.document.store.updateheader(add=True, **header_updates)

        if filename is None or filename == self.filename:
            self.document.store.save()
        else:
            self.filename = filename
            self.document.store.savefile(filename)
        self._set_saveable(False)
        return False #continue normally

    def _on_file_saveas(self, widget=None):
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK)
        # TODO: use stock text for Save as..."
        chooser = gtk.FileChooserDialog(
                _("Save as..."),
                self.main_window,
                gtk.FILE_CHOOSER_ACTION_SAVE,
                buttons
        )
        chooser.set_do_overwrite_confirmation(True)
        directory, filename = path.split(self.filename)
        chooser.set_current_name(filename)
        chooser.set_default_response(gtk.RESPONSE_OK)
        chooser.set_current_folder(directory)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            self._on_file_save(widget, filename)
            pan_app.settings.general["lastdir"] = path.dirname(filename)
            pan_app.settings.write()
        chooser.destroy()

    def _on_help_about(self, _widget=None):
        About(self.main_window)

    def _on_localization_guide(self, _widget=None):
        # Should be more redundent
        # If the guide is installed and no internet then open local
        # If Internet then go live, if no Internet or guide then disable
        openmailto.open("http://translate.sourceforge.net/wiki/guide/start")

    def _on_documentation(self, _widget=None):
        openmailto.open("http://translate.sourceforge.net/wiki/virtaal/index")

    def _on_report_bug(self, _widget=None):
        openmailto.open("http://bugs.locamotion.org/enter_bug.cgi?product=VirTaal")

    def run(self):
        gtk.main()
