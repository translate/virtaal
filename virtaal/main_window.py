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
from widgets.entry_dialog import EntryDialog
import store_grid
import unit_renderer
from about import About
import formats
import document
from support import bijection
from autocompletor import AutoCompletor
from autocorrector import AutoCorrector
from mode_selector import ModeSelector

# FIXME: Add docstrings!

def on_undo(_accel_group, acceleratable, _keyval, _modifier):
    unit_renderer.undo(acceleratable.focus_widget)

def get_data_file_abs_name(filename):
    """Get the absolute path to the given file- or directory name in VirTaal's
        data directory.

        @type  filename: str
        @param filename: The file- or directory name to look for in the data
            directory.
        """
    import sys

    BASE_DIRS = [
        os.path.dirname(unicode(__file__, sys.getfilesystemencoding())),
        os.path.dirname(unicode(sys.executable, sys.getfilesystemencoding()))
    ]

    DATA_DIRS = [
        ["..", "share", "virtaal"],
        ["share", "virtaal"]
    ]

    for basepath, data_dir in ((x, y) for x in BASE_DIRS for y in DATA_DIRS):
        dir_and_filename = data_dir + [filename]
        datafile = path.join(basepath or path.dirname(__file__), *dir_and_filename)
        if path.exists(datafile):
            return datafile
    raise Exception('Could not find "%s"' % (filename,))

def load_glade_file(filename, domain):
    gladename = get_data_file_abs_name(filename)
    gui = glade.XML(gladename, domain=domain)
    return gladename, gui

class VirTaal:
    """The entry point class for VirTaal"""

    def __init__(self, startup_file=None):
        #Set the Glade file
        self.gladefile, self.gui = load_glade_file("virtaal.glade", "virtaal")

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

        self.store_grid = None
        self.document = None

        self.autocomp = AutoCompletor()
        self.autocorr = AutoCorrector(acorpath=get_data_file_abs_name('autocorr'))

        if startup_file != None:
            self.load_file(startup_file)

    def _setup_key_bindings(self):
        self.accel_group = gtk.AccelGroup()
        self.main_window.add_accel_group(self.accel_group)
        gtk.accel_map_add_entry("<VirTaal>/Edit/Undo", gtk.keysyms.z, gdk.CONTROL_MASK)
        gtk.accel_map_add_entry("<VirTaal>/Edit/Search", gtk.keysyms.F3, 0)
        gtk.accel_map_add_entry("<VirTaal>/Navigation/Up", gtk.accelerator_parse("Up")[0], gdk.CONTROL_MASK)
        gtk.accel_map_add_entry("<VirTaal>/Navigation/Down", gtk.accelerator_parse("Down")[0], gdk.CONTROL_MASK)
        gtk.accel_map_add_entry("<VirTaal>/Navigation/PgUp", gtk.accelerator_parse("Page_Up")[0], gdk.CONTROL_MASK)
        gtk.accel_map_add_entry("<VirTaal>/Navigation/PgDown", gtk.accelerator_parse("Page_Down")[0], gdk.CONTROL_MASK)
        self.accel_group.connect_by_path("<VirTaal>/Edit/Undo", self._on_undo)
        self.accel_group.connect_by_path("<VirTaal>/Edit/Search", self._on_search)

    def _on_undo(self, _accel_group, acceleratable, _keyval, _modifier):
        unit_renderer.undo(acceleratable.focus_widget)

    def _on_search(self, _accel_group, acceleratable, _keyval, _modifier):
        self.mode_selector.select_mode_by_name('Search')

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
            (RESPONSE_SAVE, RESPONSE_DISCARD) = (gtk.RESPONSE_YES, gtk.RESPONSE_NO)
            dialog = gtk.MessageDialog(dialog,
                            gtk.DIALOG_MODAL,
                            gtk.MESSAGE_QUESTION,
                            gtk.BUTTONS_NONE,
                            _("The current file has been modified.\nDo you want to save your changes?"))
            dialog.add_buttons(gtk.STOCK_SAVE, RESPONSE_SAVE)
            dialog.add_buttons(_("_Discard"), RESPONSE_DISCARD)
            dialog.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
            dialog.set_default_response(RESPONSE_SAVE)
            response = dialog.run()
            dialog.destroy()
            if response == RESPONSE_DISCARD:
                return False
            elif response in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
                return True
            elif response == RESPONSE_SAVE:
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

    def _on_gui_mode_change(self, _mode_selector, mode):
        self.document.set_mode(mode)

    def _on_mode_change(self, _document, mode):
        self.mode_selector.set_mode(mode)

    def load_file(self, filename, dialog=None, store=None):
        """Do the actual loading of the file into the GUI"""
        if path.isfile(filename):
            try:
                self.document = document.Document(filename, store=store)
                self.document.connect('mode-changed', self._on_mode_change)
                child = self.status_box.get_children()[0]
                self.status_box.remove(child)
                child.destroy()
                self.mode_selector = ModeSelector()
                self.status_box.pack_start(self.mode_selector)
                self.status_box.reorder_child(self.mode_selector, 0)
                self.mode_selector.connect('mode-selected', self._on_gui_mode_change)
                self.document.set_mode(self.mode_selector.default_mode)

                self.filename = filename
                self.store_grid = store_grid.UnitGrid(self)
                self.store_grid.connect("modified", self._on_modified)
                child = self.sw.get_child()
                self.sw.remove(child)
                child.destroy()
                self.sw.add(self.store_grid)
                self.main_window.connect("configure-event", self.store_grid.on_configure_event)
                self.main_window.show_all()
                self.store_grid.grab_focus()
                self._set_saveable(False)
                menuitem = self.gui.get_widget("saveas_menuitem")
                menuitem.set_sensitive(True)

                self.autocomp.add_words_from_store(self.document.store)
                self.autocorr.load_dictionary(lang=pan_app.settings.language['contentlang'])
                self.store_grid.connect('cursor-changed', self._on_grid_cursor_changed)
                return True
            except IOError, e:
                dialog = gtk.MessageDialog(dialog or self.main_window,
                                gtk.DIALOG_MODAL,
                                gtk.MESSAGE_ERROR,
                                gtk.BUTTONS_OK,
                                (str(e)))
        else:
                dialog = gtk.MessageDialog(dialog or self.main_window,
                                gtk.DIALOG_MODAL,
                                gtk.MESSAGE_ERROR,
                                gtk.BUTTONS_OK,
                                _("%(filename)s does not exist." % {"filename": filename}))
        dialog.run()
        dialog.destroy()
        return False

    def _set_saveable(self, value):
        menuitem = self.gui.get_widget("save_menuitem")
        menuitem.set_sensitive(value)
        if self.filename:
            modified = ""
            if value:
                modified = "*"
            self.main_window.set_title((_('VirTaal - %(current_file)s %(modified_marker)s') % {"current_file": path.basename(self.filename), "modified_marker": modified}).rstrip())
        self.modified = value

    def _on_grid_cursor_changed(self, grid):
        assert grid is self.store_grid

        # Add words from previously handled widgets to the auto-completion list
        for textview in self.autocomp.widgets:
            buffer = textview.get_buffer()
            bufftext = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter())
            self.autocomp.add_words(self.autocomp.wordsep_re.split(bufftext))

        self.autocomp.clear_widgets()
        self.autocorr.clear_widgets()
        for target in grid.renderer.get_editor(grid).targets:
            self.autocomp.add_widget(target)
            self.autocorr.add_widget(target)

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
                _("Save"),
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
