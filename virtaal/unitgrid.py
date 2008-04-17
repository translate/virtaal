#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2007-2008 Zuza Software Foundation
# 
# This file is part of virtaal.
#
# translate is free software; you can redistribute it and/or modify
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

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import pango

from translate.storage.poheader import poheader
from translate.lang import data as langdata
from translate.lang import factory as langfactory

import Globals
from EntryDialog import *
from unitrenderer import UnitRenderer
import markup
_ = lambda x: x

(
	COLUMN_SOURCE, 
	COLUMN_TARGET,
	COLUMN_NOTE,
	COLUMN_PROGRAMMER_NOTE,
	COLUMN_TRANSLATOR_NOTE,
	COLUMN_UNIT,
        COLUMN_EDITABLE,
) = range(7)

class UnitGrid(gtk.TreeView):
    __gsignals__ = {
        'modified':(gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }
    def __init__(self, store):
        # Let's figure out if there are plurals and ensure we have everything
        nplurals = None
        if isinstance(store, poheader):
            header = store.parseheader()
            if 'Plural-Forms' in header:
                # XXX: BUG: Got files from GNOME with plurals but without this header
                nplurals, plural = store.getheaderplural()
                if nplurals is None:
                    langcode = Globals.settings.language["contentlang"]
                    self._lang = langfactory.getlanguage(langcode)
                    nplurals = self._lang.nplurals
                    plural = self._lang.pluralequation
                    while not nplurals:
                        try:
                            entry = EntryDialog("Please enter the number of noun forms (plurals) to use")
                            if entry is None:
                                return
                            nplurals = int(entry)
                        except ValueError, e:
                            continue
                        plural = EntryDialog("Please enter the plural equation to use")
                        Globals.settings.language["nplurals"] = nplurals
                        Globals.settings.language["plural"] = plural
                    store.updateheaderplural(nplurals, plural)
        self._nplurals = int(nplurals or 0)

        model = gtk.ListStore(
            gobject.TYPE_STRING,
            gobject.TYPE_STRING,
            gobject.TYPE_STRING,
            gobject.TYPE_STRING,
            gobject.TYPE_STRING,
            gobject.TYPE_PYOBJECT,
            gobject.TYPE_BOOLEAN,
        )
        for unit in store.units:
            if not unit.istranslatable():
                continue
            iter = model.append()

            model.set (iter,
               COLUMN_SOURCE, markup.markuptext(unit.source),
               COLUMN_TARGET, markup.markuptext(unit.target),
               COLUMN_NOTE, unit.getnotes() or None,
               COLUMN_PROGRAMMER_NOTE, unit.getnotes("programmer") or None,
               COLUMN_TRANSLATOR_NOTE, unit.getnotes("translator") or None,
               COLUMN_UNIT, unit,
               COLUMN_EDITABLE, False,
            )

        self.model = model
        gtk.TreeView.__init__(self, model)
        self.set_headers_visible(False)
        
        renderer = UnitRenderer(self._nplurals)
        renderer.connect("unit-edited", self.on_cell_edited, model)
        renderer.connect("modified", self._on_modified)

        column = gtk.TreeViewColumn(None, renderer, unit=COLUMN_UNIT, editable=COLUMN_EDITABLE)
        column.set_expand(True)
        self.append_column(column)
        self.targetcolumn = column

        if hasattr(self, "set_tooltip_column"):
            self.set_tooltip_column(COLUMN_NOTE)
        self.set_rules_hint(True)

        self.connect('key-press-event', self.on_key_press)
        self.connect("row-activated", self.on_row_activated)
        self.connect("cursor-changed", self.on_cursor_changed)
        self.connect("move-cursor", self.on_move_cursor)
        self.connect("button-press-event", self.on_button_press)

        self._modified_widget = None

        # This is an ugly hack to ensure that the activated path is actually 
        # drawn as editable. If it happens too soon (the widget is not yet 
        # realised) then it might end up not being in editing mode once
        # visible.
        gobject.idle_add(self._activate_editing_path, (0,))


    def on_configure_event(self, event, *user_args):
    	path, column = self.get_cursor()

    	# Horrible hack.
    	# We use set_cursor to cause the editable area to be recreated so that
    	# it can be drawn correctly. This has to be delayed (we used idle_add),
    	# since calling it immediately after columns_autosize() does not work.
    	def reset_cursor():
    		self.update_for_save()
    		self.set_cursor(path, column, start_editing=True)
    		return False

    	self.columns_autosize()
    	gobject.idle_add(reset_cursor)

    	return False

    def _on_modified(self, widget):
        self._modified_widget = widget
        self.emit("modified")
        return True
    
    def update_for_save(self, away=False):
        if self._modified_widget:
            self._modified_widget.update_for_save(away)

    def on_cell_edited(self, cell, path_string, new_target, must_advance, modified, model):
        iter = model.get_iter_from_string(path_string)
        path = model.get_path(iter)
        unit = model.get_value(iter, COLUMN_UNIT)

        if modified:
            model.set(iter, COLUMN_TARGET, markup.markuptext(new_target))
            self.emit("modified")

        model.set(iter, COLUMN_EDITABLE, False)
        if must_advance:
            self._activate_editing_path((path[0]+1,))
        return True

    def on_row_activated(self, treeview, path, view_column):
        if view_column != self.targetcolumn:
            self.set_cursor(path, self.targetcolumn, start_editing=True)
        return True
        
    def on_cursor_changed(self, treeview):
        path, column = self.get_cursor()
        
        # We defer the scrolling until GTK has finished all its current drawing
        # tasks, hence the gobject.idle_add. If we don't wait, then the TreeView
        # draws the editor widget in the wrong position. Presumably GTK issues
        # a redraw event for the editor widget at a given x-y position and then also
        # issues a TreeView scroll; thus, the editor widget gets drawn at the wrong
        # position.  
        def do_scroll():
            self.scroll_to_cell(path, self.targetcolumn, True, 0.5, 0.0)
            return False

        gobject.idle_add(do_scroll)
        
        model = treeview.get_model()
        iter = model.get_iter(path)
        if not model.get_value(iter, COLUMN_EDITABLE):
            model.set(iter, COLUMN_EDITABLE, True)
        return True

    def on_move_cursor(self, widget, step, count):
        path, column = self.get_cursor()
        iter = self.model.get_iter(path)
        if step in [gtk.MOVEMENT_DISPLAY_LINES, gtk.MOVEMENT_PAGES]:
            self.model.set(iter, COLUMN_EDITABLE, False)
        return True

    def on_button_press(self, widget, event):
#        if self._modified_widget:
#            self._modified_widget.stop_editing(canceled=False)
        # XXX - emit modified
        answer = self.get_path_at_pos(int(event.x), int(event.y))
        if answer is None:
            print "marakas! geen path gevind by (x,y) nie!"
            return True
        old_path, old_column = self.get_cursor()
        path, column, x, y = answer
        if old_path != path:
            iter = self.model.get_iter(old_path)
            self.model.set(iter, COLUMN_EDITABLE, False)
            self._activate_editing_path(path)
            self.update_for_save(away=True)
        return True

    def _activate_editing_path(self, path):
        """Activates the given path for editing."""
        try:
            iter = self.model.get_iter(path)
            self.model.set(iter, COLUMN_EDITABLE, True)
            self.set_cursor(path, self.targetcolumn, start_editing=True)
        except Exception, e:
            # Something could go wrong with .get_iter() if a non-existing path
            # was given - an expected result when trying to advance past the 
            # last row, for example
            # TODO: offer to save file, or give indication of some kind that 
            # the current run in finished
            print str(e)
            pass
        return False

    def on_key_press(self, widget, event, data=None):
    	# The TreeView does interesting things with combos like SHIFT+TAB.
    	# So we're going to stop it from doing this.
        return True

