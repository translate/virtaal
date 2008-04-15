#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright (C) 2005-2007 Osmo Salomaa
# Copyright (C) 2007 Zuza Software Foundation
#
# This file was part of Gaupol.
# This file is part of Translate.
#
# Gaupol is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# Translate is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# Translate.  If not, see <http://www.gnu.org/licenses/>.

"""Cell renderer for multiline text data."""

import gobject
import gtk
from gtk import keysyms
import pango
try:
    import gtkspell
except ImportError, e:
    gtkspell = None
import re
import sys

from translate.misc.multistring import multistring

import Globals
import markup

import weakref
import undo_buffer

_ = lambda x: x

first_word_re = re.compile("(?m)(?u)^(<[^>]+>|\\\\[nt]|[\W$^\n])*(\\b|\\Z)")
"""A regular expression to help us find a meaningful place to position the 
cursor initially."""

def on_size_allocate(widget, allocation):
    widget.child.set_size_request(allocation.width - 2, -1)


def undo(tree_view):
    undo_buffer.undo(CellUnitView.undo_list[tree_view.get_buffer()])


class CellUnitView(gtk.EventBox, gtk.CellEditable):
    """Text view suitable for cell renderer use."""
    
    __gtype_name__ = "CellUnitView"
    
    __gsignals__ = {
        'modified':(gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }
    
    
    __unit_buffers = weakref.WeakKeyDictionary()
    undo_list    = weakref.WeakKeyDictionary()
    
        
    def __init__(self, nplurals=None):
        gtk.EventBox.__init__(self)
#        self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(0, 0, 50000))

        self.table = gtk.Table(rows=1, columns=4, homogeneous=True)
        self.add(self.table)

        self.vbox = gtk.VBox()

        self.table.attach(self.vbox, 1, 3, 0, 1, xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.FILL|gtk.EXPAND)

        self.textviews = []
        self.recent_textview = None
        self.buffers = []
        self._modified = False

        copy_button = gtk.Button(_("_Copy original"))
        copy_button.connect("activate", self._on_copy_original)
        copy_button.connect("clicked", self._on_copy_original)
        copy_button.set_relief(gtk.RELIEF_NONE)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_NONE), expand=False, fill=False)
        hbox.pack_start(copy_button, expand=False, fill=False)

        #TODO: get these state like variables from the format
        # eg, fuzzy for PO, or approved, etc. for XLIFF
        self.fuzzy_checkbox = gtk.CheckButton(_("F_uzzy"))
        self.fuzzy_checkbox.connect("toggled", self._on_modified)
        hbox.pack_start(self.fuzzy_checkbox, expand=False, fill=False)
        self.vbox.pack_end(hbox, expand=False, fill=False)
#        self.set_flags(gtk.NO_WINDOW)

        self.must_advance = False
        self._unit = None
        self._nplurals = nplurals

    def do_editing_done(self, *args):
        """End editing."""
        self.update_for_save()
        self.remove_widget()

    def do_remove_widget(self, *args):
        """Remove widget."""
        pass

    def do_start_editing(self, *args):
        """Start editing."""
        self.textviews[0].grab_focus()

    def _on_focus(self, widget, direction):
        self.recent_textview = widget
        return False

    def _on_modified(self, widget):
        if widget in self.buffers:
            self.fuzzy_checkbox.set_active(False)
        elif self.recent_textview:
            self.recent_textview.grab_focus()
        self.emit("modified")
        self._modified = True
        return False

    def update_for_save(self):
        self.get_unit()
        self.reset_modified()

    def get_modified(self):
        return self._modified

    def reset_modified(self):
        """Resets all the buffers to not modified."""
        map(lambda b: b.set_modified(False), self.buffers)
        self._modified = False

    def get_text(self):
        targets = map(lambda b:b.props.text, self.buffers)
        if len(targets) == 1:
            return targets[0]
        else:
            return multistring(targets)

    def get_unit(self):
        """Get the text."""
        #XXX comments?
        self._unit.target = markup.unescape(self.get_text())
        self._unit.markfuzzy(self.fuzzy_checkbox.get_active())
        return self._unit

    def set_unit(self, unit):
        """Set the text."""
        self._unit = unit
        if unit is None:
            return

        width, height = self.get_size_request()
#        self.vbox.set_size_request(width / 2, height)

        if unit.hasplural():
            sources = unit.source.strings
            targets = unit.target.strings
            nplurals = self._nplurals
            if len(targets) != nplurals:
                targets = targets[:nplurals]
                targets.extend([u""]* (nplurals-len(targets)))
        else:
            sources = [unit.source]
            targets = [unit.target]
            self._nplurals = 1
        
        for source in sources:
            label = gtk.Label()
            label.set_markup(markup.markuptext(source))
            label.set_line_wrap(True)
            label.set_selectable(True)
            scrolledwindow = gtk.ScrolledWindow()
            scrolledwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
            scrolledwindow.add_with_viewport(label)
            scrolledwindow.child.connect('size-allocate', on_size_allocate)
            self.vbox.pack_start(scrolledwindow, expand=True, fill=True)

    #        source_view = self.source_view = gtk.TextView()
    #        source_view.connect("key-press-event", self._on_textview_key_press_event)
    #        source_view.set_border_window_size(gtk.TEXT_WINDOW_BOTTOM, 1)
    #        source_view.set_wrap_mode(gtk.WRAP_WORD)
    #        buffer = source_view.get_buffer()
    #        buffer.set_text(markup.escape(unit.source))
    #        source_view.set_editable(False)
    #        scrolledwindow = gtk.ScrolledWindow()
    #        scrolledwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
    #        scrolledwindow.add(source_view)
    #        self.vbox.pack_start(scrolledwindow, expand=True, fill=True)

        global gtkspell

        if unit not in CellUnitView.__unit_buffers:
            CellUnitView.__unit_buffers[unit] = []
            
            for buffer, undo_list in [undo_buffer.make_undo_buffer() for target in targets]:
                CellUnitView.__unit_buffers[unit].append(buffer)
                CellUnitView.undo_list[buffer] = undo_list
        
        for target, buffer in zip(targets, CellUnitView.__unit_buffers[unit]):
            textview = gtk.TextView(buffer)
            if gtkspell:
                try:
                    spell = gtkspell.Spell(textview)
                    spell.set_language(Globals.settings.language["contentlang"])
                except Exception, e:
                    print >> sys.stderr, _("Could not initialize spell checking")
                    print >> sys.stderr, str(e)
                    gtkspell = None
            textview.set_wrap_mode(gtk.WRAP_WORD)
            textview.set_border_window_size(gtk.TEXT_WINDOW_TOP, 1)
            textview.connect("key-press-event", self._on_textview_key_press_event)
            textview.connect("focus-in-event", self._on_focus)
            self.textviews.append(textview)

            scrolledwindow = gtk.ScrolledWindow()
            scrolledwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
            scrolledwindow.add(textview)
            self.vbox.pack_start(scrolledwindow, expand=True, fill=True)
            textview.connect("move-cursor", self._on_source_scroll)
#            textview.connect("insert-at-cursor", self._on_insert_at_cursor)
#            textview.connect("move-viewport", self._on_source_scroll)
#            textview.connect("set-scroll-adjustments", self._on_source_scroll)

            buffer = textview.get_buffer()
            undo_buffer.execute_without_signals(buffer, lambda: buffer.set_text(markup.escape(target)))
            buffer.set_modified(False)

            buffer.connect("modified-changed", self._on_modified)
            self.buffers.append(buffer)
        
        # Let's show_all now while most of the important things are in place
        # We'll show_all again later
        self.show_all()
        #XXX - markup
        self._place_cursor()
        self.recent_textview = self.textviews[0]
        self.recent_textview.place_cursor_onscreen()
        self.fuzzy_checkbox.set_active(unit.isfuzzy())

        # comments
        developer_comments = unit.getnotes("developer")
        translator_comments = unit.getnotes("translator")

        vbox = gtk.VBox()
        self.table.attach(vbox, 0, 1, 0, 1, xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.FILL|gtk.EXPAND)
        if developer_comments:
            frame = gtk.Frame(_("Developer comments"))
            vbox.pack_start(frame)
            frame.set_border_width(2)
            frame.set_label_align(1.0, 0.5)
            frame.connect('size-allocate', on_size_allocate)
            label = gtk.Label(developer_comments)
            frame.add(label)
            label.set_alignment(xalign=0.0, yalign=0.0)
            label.set_line_wrap(True)

        if translator_comments:
            frame = gtk.Frame(_("Translator comments"))
            vbox.pack_end(frame)
            frame.set_border_width(2)
            frame.set_label_align(1.0, 0.5)
            frame.connect('size-allocate', on_size_allocate)
            label = gtk.Label(translator_comments)
            frame.add(label)
            label.set_alignment(xalign=0.0, yalign=0.0)
            label.set_line_wrap(True)

        self.show_all()
        self.reset_modified()

    def _place_cursor(self, index=0):
        """Place the cursor in a place, trying to guess a useful starting point."""
        buffer = self.buffers[index]
        text = buffer.props.text
        if not text:
            return
        # TODO: handle a non-match (re is supposed to be impossible not to match)
        translation_start = first_word_re.match(text).span()[1]
        buffer.place_cursor(buffer.get_iter_at_offset(translation_start))

    def _on_textview_key_press_event(self, textview, event):
        """Handle special keypresses in the textarea."""
        # End editing on <Return>
        if event.keyval == keysyms.Return or event.keyval == keysyms.KP_Enter:
            if self._nplurals == 1 or self.textviews.index(textview) == self._nplurals - 1:
                self.must_advance = True
                self.editing_done()
            else:
                new_index = self.textviews.index(textview) + 1
                self.textviews[new_index].grab_focus()
                self._place_cursor(new_index)
            return True
        # Automatically move to the next line if \n is entered
        if event.keyval == keysyms.n:
            buffer = textview.get_buffer()
            cursor_position = buffer.get_iter_at_offset(buffer.props.cursor_position)
            one_back = buffer.get_iter_at_offset(buffer.props.cursor_position-1)
            previous = buffer.get_text(one_back, cursor_position)
            if previous == '\\':
                buffer.insert_at_cursor('n\n')
                self.recent_textview.place_cursor_onscreen()
            else:
                # Just a normal 'n' - nothing special
                buffer.insert_at_cursor('n')
            # We have to return true, otherwise another 'n' will be inserted
            return True
        return False

    def _on_source_scroll(self, textview, step_size, count, extend_selection):
        #XXX scroll the source???
        return True

    def _on_insert_at_cursor(self, textview, string):
        return True

    def _on_copy_original(self, widget):
        for buffer in self.buffers:
            buffer.set_text(markup.escape(self._unit.source))
            self._place_cursor()
        return True


class UnitRenderer(gtk.GenericCellRenderer):
    """Cell renderer for multiline text data."""

    __gtype_name__ = "UnitRenderer"
    __gproperties__ = {
        "unit":     (gobject.TYPE_PYOBJECT, 
                    "The unit",
                    "The unit that this renderer is currently handling",
                    gobject.PARAM_READWRITE),
        "editable": (gobject.TYPE_BOOLEAN,
                    "editable", 
                    "A boolean indicating whether this unit is currently editable",
                    False,
                    gobject.PARAM_READWRITE),
    }
 
    __gsignals__ = {
        "unit-edited":  (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                        (gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN)),
        "modified":     (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }

    def __init__(self, nplurals=None):
        gtk.GenericCellRenderer.__init__(self)
        self.set_property('mode', gtk.CELL_RENDERER_MODE_EDITABLE)

        self.unit = None
        self.editable = False
        self._editor = None
        self._nplurals = nplurals

    def init_widget(self):
        if self.unit.isfuzzy():
            self.props.cell_background = "gray"
            self.props.cell_background_set = True
#            self.style.base[gtk.
        else:
            self.props.cell_background_set = False

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)
        if pspec.name == 'unit':
            self.init_widget()

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def on_render(self, window, widget, background_area, cell_area, expose_area, flags):
        if self.editable:
            return True
        x_offset, y_offset, width, height = self.do_get_size(widget, cell_area)
#        halfwidth = width / 2 - x_offset * 2
#        source_layout = self.get_layout(widget, self.unit.source, halfwidth)
#        target_layout = self.get_layout(widget, self.unit.target, halfwidth)

#        window.draw_layout(widget.get_pango_context(), cell_area.x, cell_area.y, layout)
#        widget.get_style().paint_layout(window, gtk.STATE_NORMAL, True, 
#                cell_area, widget, '', cell_area.x + x_offset, 
#                cell_area.y + y_offset, source_layout)
#        widget.get_style().paint_layout(window, gtk.STATE_NORMAL, True, 
#                cell_area, widget, '', cell_area.x + x_offset + width/2, 
#                cell_area.y + y_offset, target_layout)
        x = cell_area.x + x_offset
        y = cell_area.y + y_offset
        widget.get_style().paint_layout(window, gtk.STATE_NORMAL, True, 
                cell_area, widget, '', x, y, self.source_layout)
        widget.get_style().paint_layout(window, gtk.STATE_NORMAL, True, 
                cell_area, widget, '', x + width/2, y, self.target_layout)

    def get_layout(self, widget, text, width):
        '''Gets the Pango layout used in the cell in a TreeView widget.'''
        layout = pango.Layout(widget.get_pango_context())
        layout.set_wrap(pango.WRAP_WORD_CHAR)
        layout.set_width(width * pango.SCALE)

        #XXX - plurals?
        text = text or ""
#        layout.set_text(text)
        layout.set_markup(markup.markuptext(text))
        return layout

    def do_get_size(self, widget, cell_area):
        xpad = 2
        ypad = 2

        #TODO: store last unitid and computed dimensions

        width = widget.get_toplevel().get_allocation().width - 32
        self.source_layout = self.get_layout(widget, self.unit.source, width / 2)
        self.target_layout = self.get_layout(widget, self.unit.target, width / 2)
        layout_width, source_height = self.source_layout.get_pixel_size()
        layout_width, target_height = self.target_layout.get_pixel_size()

#        unit = self.unit
#        source = unit.source
#        target = unit.target
#        if len(target) < len(source) / 2:
#            target = source
#        layout = self.get_layout(widget, '\n'.join([source, target, unit.getcontext()]), width / 2)
#        layout_width, height = layout.get_pixel_size()

        if self.editable:
#            height = height * 2 + 34
            if self.unit.hasplural():
                # Don't change without testing in languages with lots of plurals
                height = (source_height + 2) * 2 + (target_height + 4) * self._nplurals + 32
            else:
                height = max(source_height, target_height) * 2 + 34
#                height = source_height + target_height + 30
        else:
            height = max(source_height, target_height)

        # XXX - comments

        # TODO: remove these:
        x_offset = xpad
        y_offset = ypad

        width  = width  + (xpad * 2)
        height = height + (ypad * 2)

        height = min(height, 600)
        return x_offset, y_offset, width, height

    def _on_editor_done(self, editor):
        self.emit("unit-edited", editor.get_data("path"), editor.get_text(), editor.must_advance, editor.get_modified())
        return True

    def _on_modified(self, editor):
        self._modified_widget = editor
        self.emit("modified")
        return True

    def update_for_save(self, away=False):
        """Prepare all data structures for saving.

        away indicates that this is because we want to move to another cell."""
        if self._modified_widget:
            self._modified_widget.update_for_save()
#            if away:
#                self._modified_widget.editing_done()

    def do_start_editing(self, event, widget, path, bg_area, cell_area, flags):
        """Initialize and return the editor widget."""
        editor = CellUnitView(self._nplurals)
        editor.set_unit(self.unit)
        editor.set_size_request(cell_area.width, cell_area.height-2)
        editor.set_border_width(min(self.props.xpad, self.props.ypad))
        editor.set_data("path", path)
        editor.connect("editing-done", self._on_editor_done)
        editor.connect("modified", self._on_modified)
        editor.show()
        widget.editor = editor
        self._editor = editor
        return editor
