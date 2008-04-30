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

from unit_renderer import UnitRenderer
from virtaal.support import bijection

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
        self.document.set_mode('Default')
        # Create a bidirectional mapping between TreeView indices and
        # translation unit indices (thus, we have
        # B: TreeView index <-> Translation unit index. This is necessary
        # because not all translation units are displayed and thus when we
        # are given a TreeView index, we need to be able to compute how it
        # relates to the index of its unit in the translation store.
        self.display_index = bijection.Bijection(enumerate(self.document.mode))
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
        self.connect("cursor-changed", self.on_cursor_changed)
        self.connect("button-press-event", self.on_button_press)

        #self.accel_group = gtk.AccelGroup()
        #self.add_accel_group(self.accel_group)

        self._owner.accel_group.connect_by_path("<VirTaal>/Navigation/Up", self._on_move_up)
        self._owner.accel_group.connect_by_path("<VirTaal>/Navigation/Down", self._on_move_down)

        gobject.idle_add(self._activate_editing_path, (0,), (0,))

    def _activate_editing_path(self, old_path, path):
        """Activates the given path for editing."""
        item_index = self.display_index[path[0]]
        self.document.mode.cursor = self.document.mode.get_cursor(item_index)
        self.get_model().set(self.get_model().get_iter(old_path), COLUMN_EDITABLE, False)
        self.get_model().set(self.get_model().get_iter(path),     COLUMN_EDITABLE, True)
        def change_cursor():
            self.set_cursor(path, self.targetcolumn, start_editing=True)
        gobject.idle_add(change_cursor, priority=gobject.PRIORITY_DEFAULT_IDLE)

    def _move(self, offset):
        try:
            path, _column = self.get_cursor()
            self._activate_editing_path(path, (path[0] + offset,))
        except KeyError:
            pass

        return True

    def _on_move_up(self, accel_group, acceleratable, keyval, modifier):
        return self._move(-1)

    def _on_move_down(self, accel_group, acceleratable, keyval, modifier):
        return self._move(1)

    def on_button_press(self, _widget, event):
        answer = self.get_path_at_pos(int(event.x), int(event.y))
        if answer is None:
            print "marakas! geen path gevind by (x,y) nie!"
            return True
        old_path, _old_column = self.get_cursor()
        path, _column, _x, _y = answer
        if old_path != path:
            self._activate_editing_path(old_path, path)
        return True

    def on_configure_event(self, _event, *_user_args):
        path, column = self.get_cursor()

        # Horrible hack.
        # We use set_cursor to cause the editable area to be recreated so that
        # it can be drawn correctly. This has to be delayed (we used idle_add),
        # since calling it immediately after columns_autosize() does not work.
        def reset_cursor():
            self.set_cursor(path, column, start_editing=True)
            return False

        self.columns_autosize()
        gobject.idle_add(reset_cursor)

        return False

    def _on_modified(self, widget):
        self.emit("modified")
        return True

    def on_cell_edited(self, _cell, path_string, must_advance, modified, model):
        if must_advance:
            return self._move(self.document.mode.current, self.document.mode.next)
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
        return True

    def on_key_press(self, _widget, _event, _data=None):
        # The TreeView does interesting things with combos like SHIFT+TAB.
        # So we're going to stop it from doing this.
        return True

