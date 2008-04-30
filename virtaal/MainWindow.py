#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2007-2008 Zuza Software Foundation
# 
# This file is part of virtaal.
#
# virtaal is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with translate; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import sys

try:
    import pygtk
    pygtk.require("2.0")
except:
    pass

import gtk.glade

import os.path as path
import time

from translate.storage import factory
from translate.storage import poheader

import Globals
from EntryDialog import EntryDialog
import unitgrid
import unitrenderer
from about import About
import formats
import document

_ = lambda x: x

def on_undo(_accel_group, acceleratable, _keyval, _modifier):
    unitrenderer.undo(acceleratable.focus_widget)

TEXT_VIEW_ACCELS = gtk.AccelGroup()
key, modifier = gtk.accelerator_parse("<Control>z")
TEXT_VIEW_ACCELS.connect_group(key, modifier, gtk.ACCEL_VISIBLE, on_undo)


class VirTaal:

    def __init__(self, basepath=None):
            
        #Set the Glade file
        self.gladefile = path.join(basepath or path.dirname(__file__), "data", "virtaal.glade")
        self.gui = gtk.glade.XML(self.gladefile)
        
        #Create our dictionay and connect it
        dic = { 
                "on_mainwindow_destroy" : gtk.main_quit,
                "on_mainwindow_delete" : self._on_mainwindow_delete,
                "on_open_activate" : self._on_file_open,
                "on_save_activate" : self._on_file_save,
                "on_saveas_activate" : self._on_file_saveas,
                "on_about_activate" : self._on_help_about,
                }
        self.gui.signal_autoconnect(dic)

        self.sw = self.gui.get_widget("scrolledwindow1")
        edit_menu = self.gui.get_widget("menuitem2")
        edit_menu.set_sensitive(False)
        self.main_window = self.gui.get_widget("MainWindow")
        self.main_window.add_accel_group(TEXT_VIEW_ACCELS)
        self.main_window.show()

        self.modified = False
        self.filename = None
        
        self.translation_store = None
        self.unit_grid = None

    def _on_mainwindow_delete(self, _widget, _event):
        if self.modified:
            dialog = gtk.MessageDialog(self.main_window,
                            gtk.DIALOG_MODAL,
                            gtk.MESSAGE_QUESTION,
                            gtk.BUTTONS_YES_NO,
                            _("The current file was modified, but is not yet saved. Are you sure you want to leave without saving?"))
            dialog.set_default_response(gtk.RESPONSE_NO)
            response = dialog.run()
            dialog.destroy()
            if response in [gtk.RESPONSE_NO, gtk.RESPONSE_DELETE_EVENT]:
                return True
        return False

    def _on_file_open(self, _widget, destroyCallback=None):
        chooser = formats.file_open_chooser(destroyCallback)
        chooser.set_transient_for(self.main_window)
        
        while True:
            response = chooser.run()
            if response == gtk.RESPONSE_OK:
                filename = chooser.get_filename()
                Globals.settings.general["lastdir"] = path.dirname(filename)
                Globals.settings.write()
                if self.open_file(filename, chooser):
                    break
            elif response == gtk.RESPONSE_CANCEL or \
                    response == gtk.RESPONSE_DELETE_EVENT:
                break

        chooser.destroy()

    def open_file(self, filename, dialog):
        if self.modified:
            dialog = gtk.MessageDialog(dialog,
                            gtk.DIALOG_MODAL,
                            gtk.MESSAGE_QUESTION,
                            gtk.BUTTONS_YES_NO,
                            _("The current file was modified, but is not yet saved. Are you sure you want to open a new file without saving the previous one?"))
            dialog.set_default_response(gtk.RESPONSE_NO)
            response = dialog.run()
            dialog.destroy()
            if response in [gtk.RESPONSE_NO, gtk.RESPONSE_DELETE_EVENT]:
                return True

        if filename == self.filename:
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

    def load_file(self, filename, dialog=None):
        """Do the actual loading of the file into the GUI"""
        try:
            self.translation_store = factory.getobject(filename)
            self.unit_grid = unitgrid.UnitGrid(self.translation_store)
            self.unit_grid.connect("modified", self._on_modified)
            self.sw.remove(self.sw.get_child())
            self.sw.add(self.unit_grid)
            self.main_window.connect("configure-event", self.unit_grid.on_configure_event)
            self.main_window.show_all()
            self.unit_grid.grab_focus()
            self.document = document.Document(factory.getobject(filename))
        except Exception, e:
            dialog = gtk.MessageDialog(dialog or self.main_window,
                            gtk.DIALOG_MODAL,
                            gtk.MESSAGE_ERROR,
                            gtk.BUTTONS_OK,
                            (str(e)))
            dialog.run()
            dialog.destroy()
            return False

        # Now we can change state (filename, save states, etc.)
        self.filename = filename
        self.unit_grid = unitgrid.UnitGrid(self.document)
        self.unit_grid.connect("modified", self._on_modified)
        self.sw.remove(self.sw.get_child())
        self.sw.add(self.unit_grid)
        self.main_window.connect("configure-event", self.unit_grid.on_configure_event)
        self.main_window.show_all()
        self.unit_grid.grab_focus()
        self._set_saveable(False)
        self.main_window.set_title(path.basename(filename))
        self._set_saveable(False)
        menuitem = self.gui.get_widget("saveas_menuitem")
        menuitem.set_sensitive(True)
        return True

    def _set_saveable(self, value):
        menuitem = self.gui.get_widget("save_menuitem")
        menuitem.set_sensitive(value)
        self.modified = value

    def _on_modified(self, _widget):
        if not self.modified:
            self.main_window.set_title("* " + self.main_window.get_title())
            self._set_saveable(True)

    def _on_file_save(self, _widget, filename=None):
        if self.modified:
            self.unit_grid.update_for_save()
        if filename is None or filename == self.filename:
            if isinstance(self.translation_store, poheader.poheader):
                name = Globals.settings.translator["name"]
                email = Globals.settings.translator["email"]
                team = Globals.settings.translator["team"]
                if not name:
                    name = EntryDialog(_("Please enter your name"))
                    if name is None:
                        # User cancelled
                        return
                    Globals.settings.translator["name"] = name
                if not email:
                    email = EntryDialog(_("Please enter your e-mail address"))
                    if email is None:
                        # User cancelled
                        return
                    Globals.settings.translator["email"] = email
                if not team:
                    team = EntryDialog(_("Please enter your team's information"))
                    if team is None:
                        # User cancelled
                        return
                    Globals.settings.translator["team"] = team
                Globals.settings.write()
                po_revision_date = time.strftime("%F %H:%M%z")
                header_updates = {}
                header_updates["PO_Revision_Date"] = po_revision_date
                header_updates["X_Generator"] = Globals.x_generator
                if name or email:
                    header_updates["Last_Translator"] = u"%s <%s>" % (name, email)
                    self.translation_store.updatecontributor(name, email)
                if team:
                    header_updates["Language-Team"] = team
                self.translation_store.updateheader(add=True, **header_updates)
                
            self.translation_store.save()
        else:
            self.filename = filename
            self.translation_store.savefile(filename)
        self._set_saveable(False)
        self.main_window.set_title(path.basename(self.filename))

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
            Globals.settings.general["lastdir"] = path.dirname(filename)
            Globals.settings.write()
        chooser.destroy()
            
    def _on_help_about(self, widget=None):
        About(self.main_window)

    def run(self):
        if len(sys.argv) > 1:
            self.load_file(sys.argv[1])
        gtk.main()

#    import hotshot
#    prof = hotshot.Profile("virtaal.prof")
#    prof.runcall(gtk.main)
#    prof.close()
