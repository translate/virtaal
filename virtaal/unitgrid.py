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

import pygtk
pygtk.require('2.0')
import gtk
import gobject

from unitrenderer import UnitRenderer

COLUMN_NOTE, COLUMN_UNIT, COLUMN_EDITABLE = 0, 1, 2

class UnitGrid(gtk.TreeView):
    __gsignals__ = {
        'modified':(gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }
    
    document = property(lambda self: self._owner.document)
    
    def __init__(self, owner):
        gtk.TreeView.__init__(self, gtk.ListStore(gobject.TYPE_STRING, 
                                                  gobject.TYPE_PYOBJECT, 
                                                  gobject.TYPE_BOOLEAN))

        self._owner = owner

        # The default mode should give us all the units we need
        for unit in (self.document.store.units[i] for i in self.document.mode):
            itr = self.get_model().append()

            self.get_model().set (itr,
               COLUMN_NOTE, unit.getnotes() or None,
               COLUMN_UNIT, unit,
               COLUMN_EDITABLE, False,
            )

        self.set_headers_visible(False)
        self.set_direction(gtk.TEXT_DIR_LTR)
        
        if len(model) == 0:
            raise ValueError(_("The file did not contain anything to translate."))
            
        renderer = UnitRenderer(self)
        renderer.connect("editing-done", self.on_cell_edited, self.get_model())
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

        gobject.idle_add(self._activate_editing_path, (0,))


    def on_configure_event(self, _event, *_user_args):
        path, column = self.get_cursor()

        # Horrible hack.
        # We use set_cursor to cause the editable area to be recreated so that
        # it can be drawn correctly. This has to be delayed (we used idle_add),
        # since calling it immediately after columns_autosize() does not work.
        def reset_cursor():
            #self.update_for_save()
            self.set_cursor(path, column, start_editing=True)
            return False

        self.columns_autosize()
        gobject.idle_add(reset_cursor)

        return False

    def _on_modified(self, widget):
        self.emit("modified")
        return True
    
    def on_cell_edited(self, _cell, path_string, must_advance, modified, model):
        itr = model.get_iter_from_string(path_string)
        path = model.get_path(itr)

#        if modified:
#            model.set(itr, COLUMN_TARGET, markup.markuptext(new_target))
#            self.emit("modified")

        if must_advance:
            new_path = (path[0]+1,)
            if new_path[0] < model.iter_n_children(None):
                model.set(itr, COLUMN_EDITABLE, False)
                self._activate_editing_path(new_path)
        return True

    def on_row_activated(self, _treeview, path, view_column):
        if view_column != self.targetcolumn:
            self.set_cursor(path, self.targetcolumn, start_editing=True)
        return True
        
    def on_cursor_changed(self, treeview):
        path, _column = self.get_cursor()
        
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
        itr = model.get_iter(path)
        if not model.get_value(itr, COLUMN_EDITABLE):
            model.set(itr, COLUMN_EDITABLE, True)
        return True

    def on_move_cursor(self, _widget, step, _count):
        path, _column = self.get_cursor()
        itr = self.get_model().get_iter(path)
        if step in [gtk.MOVEMENT_DISPLAY_LINES, gtk.MOVEMENT_PAGES]:
            self.get_model().set(itr, COLUMN_EDITABLE, False)
        return True

    def on_button_press(self, _widget, event):
#        if self._modified_widget:
#            self._modified_widget.stop_editing(canceled=False)
        # XXX - emit modified
        answer = self.get_path_at_pos(int(event.x), int(event.y))
        if answer is None:
            print "marakas! geen path gevind by (x,y) nie!"
            return True
        old_path, _old_column = self.get_cursor()
        path, _column, _x, _y = answer
        if old_path != path:
            itr = self.get_model().get_iter(old_path)
            self.get_model().set(itr, COLUMN_EDITABLE, False)
            self._activate_editing_path(path)
            #self.update_for_save(away=True)
        return True

    def _activate_editing_path(self, path):
        """Activates the given path for editing."""
        try:
            itr = self.get_model().get_iter(path)
            self.get_model().set(itr, COLUMN_EDITABLE, True)
            self.set_cursor(path, self.targetcolumn, start_editing=True)
        except:
            # Something could go wrong with .get_iter() if a non-existing path
            # was given - an expected result when trying to advance past the 
            # last row, for example
            # TODO: offer to save file, or give indication of some kind that 
            # the current run in finished            test_code = ""
            import traceback
            import sys
            
            print "Exception in user code:"
            print '-'*60
            traceback.print_exc(file=sys.stdout)
            print '-'*60                    

        return False

    def on_key_press(self, _widget, _event, _data=None):
        # The TreeView does interesting things with combos like SHIFT+TAB.
        # So we're going to stop it from doing this.
        return True

