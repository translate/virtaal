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
import re

import gobject
import pango
import gtk
try:
    import gtkspell
except ImportError, e:
    gtkspell = None

from translate.misc.multistring import multistring

import markup
import unit_layout
from simplegeneric import generic
import Globals
from Globals import _
import label_expander


@generic
def v_padding(layout):
    raise NotImplementedError()

@v_padding.when_type(unit_layout.VList)
def v_padding_v_list(_v_list):
    return 2

@v_padding.when_type(unit_layout.HList)
def v_padding_h_list(_h_list):
    return 2

@v_padding.when_type(unit_layout.TextBox)
def v_padding_text_box(_text_box):
    return 2


@generic
def h_padding(layout):
    raise NotImplementedError()

@h_padding.when_type(unit_layout.VList)
def h_padding_v_list(_v_list):
    return 2

@h_padding.when_type(unit_layout.HList)
def h_padding_h_list(_h_list):
    return 2

@h_padding.when_type(unit_layout.TextBox)
def h_padding_text_box(_text_box):
    return 2


@generic
def height(layout, widget, width):
    raise NotImplementedError()

@height.when_type(unit_layout.Layout)
def height_layout(layout, widget, width):
    return height(layout.child, widget, width / 2)

@height.when_type(unit_layout.VList)
def height_v_list(v_list, widget, width):
    item_width = (width - len(v_list.children) * (h_padding(v_list) + 1)) / len(v_list.children)
    return 2*v_padding(v_list) + max(height(child, widget, item_width) for child in v_list.children)

@height.when_type(unit_layout.HList)
def height_h_list(h_list, widget, width):
    return sum(height(child, widget, (width - 2*h_padding(h_list))) for child in h_list.children) + \
           len(h_list.children) * (v_padding(h_list) + 1)

@height.when_type(unit_layout.TextBox)
def height_text_box(text_box, widget, width):
    # TODO: The calculations here yield incorrect results. We'll have to look at this.    
    pango_layout = widget.create_pango_layout(text_box.get_text())
    pango_layout.set_width(width * pango.SCALE)
    pango_layout.set_wrap(pango.WRAP_WORD)
    pango_layout.set_markup(text_box.get_text())
    _w, h = pango_layout.get_pixel_size()
    
    return h + 8 # XXX: The added 8 is bogus.

@height.when_type(label_expander.LabelExpander)
def height_label_expander(text_box, widget, width):
    return 100 # XXX: Compute the height!


@generic
def make_widget(layout):
    raise NotImplementedError()

@make_widget.when_type(unit_layout.Layout)
def make_layout(layout):
    table = gtk.Table(rows=1, columns=4, homogeneous=True)
    names = {layout.name: table}
    child, child_names = make_widget(layout.child)
    table.attach(child, 1, 3, 0, 1, xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.FILL|gtk.EXPAND)
    names.update(child_names)
    return table, names

def fill_list(lst, box):
    names = {lst.name: box}
    for child in lst.children:
        child_widget, child_names = make_widget(child)
        box.pack_start(child_widget, fill=True, expand=True)
        names.update(child_names)
    return box, names

@make_widget.when_type(unit_layout.VList)
def make_vlist(layout):
    return fill_list(layout, gtk.VBox())#homogeneous=False))

@make_widget.when_type(unit_layout.HList)
def make_hlist(layout):
    return fill_list(layout, gtk.HBox())#homogeneous=False))

@make_widget.when_type(unit_layout.TextBox)
def make_text_box(layout):
    text_view = gtk.TextView()

    global gtkspell
    if gtkspell:
        try:
            spell = gtkspell.Spell(text_view)
            spell.set_language(Globals.settings.language["contentlang"])
        except:
            import traceback
            
            print >> sys.stderr, _("Could not initialize spell checking")
            traceback.print_exc(file=sys.stderr)
            gtkspell = None

    text_view.get_buffer().set_text(layout.get_text())
    def on_change(buf):
        layout.set_text(buf.get_text(buf.get_start_iter(), buf.get_end_iter()))
    text_view.get_buffer().connect('changed', on_change)
    text_view.set_wrap_mode(gtk.WRAP_WORD)
    text_view.set_border_window_size(gtk.TEXT_WINDOW_TOP, 1)

    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
    scrolled_window.add(text_view)

    scrolled_window.connect('size-allocate', on_size_allocate)

    return scrolled_window, {layout.name: scrolled_window}

#A regular expression to help us find a meaningful place to position the 
#cursor initially.
first_word_re = re.compile("(?m)(?u)^(<[^>]+>|\\\\[nt]|[\W$^\n])*(\\b|\\Z)")

def on_size_allocate(widget, allocation):
    # TODO: replace the 2 in allocation.width - 2 with a GTK function which
    # gives the border width of widget.
    widget.child.set_size_request(allocation.width - 2, -1)


class UnitEditor(gtk.EventBox, gtk.CellEditable):
    """Text view suitable for cell renderer use."""
    
    __gtype_name__ = "UnitEditor"
    
    __gsignals__ = {
        'modified':(gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }
   
    def __init__(self, parent, unit):
        gtk.EventBox.__init__(self)
#        self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(0, 0, 50000))

        self.layout, widget_dict = make_widget(unit_layout.get_blueprints(unit, parent))
        self.add(self.layout)

        #blueprints['copy_button'].connect("activate", self._on_copy_original)
        #editor_names['copy_button'].connect("clicked", self._on_copy_original)
        #editor_names['copy_button'].set_relief(gtk.RELIEF_NONE)

        #editor_names['fuzzy_checkbox'].connect("toggled", self._on_modified)

        self.must_advance = False
        self._modified = False
        self._unit = unit
        self._widget_dict = widget_dict

#        self._place_cursor()
#        self.recent_textview = self.textviews[0]
#        self.recent_textview.place_cursor_onscreen()
#        self.fuzzy_checkbox.set_active(unit.isfuzzy())


    def do_editing_done(self, *_args):
        """End editing."""
        self.update_for_save()
        self.remove_widget()

    def do_remove_widget(self, *_args):
        """Remove widget."""
        pass

    def do_start_editing(self, *_args):
        """Start editing."""
        self._widget_dict['source-0'].grab_focus()
        #self.textviews[0].grab_focus()

    def _on_focus(self, widget, _direction):
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
        for b in self.buffers:
            b.set_modified(False)
        self._modified = False

    def get_text(self):
        targets = [b.props.text for b in self.buffers]
        if len(targets) == 1:
            return targets[0]
        else:
            return multistring(targets)

    def _place_cursor(self, index=0):
        """Place the cursor in a place, trying to guess a useful starting point."""
        buf = self.buffers[index]
        text = buf.props.text
        if not text:
            return
        # TODO: handle a non-match (re is supposed to be impossible not to match)
        translation_start = first_word_re.match(text).span()[1]
        buf.place_cursor(buf.get_iter_at_offset(translation_start))

    def _on_textview_key_press_event(self, textview, event):
        """Handle special keypresses in the textarea."""
        # End editing on <Return>
        if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
            if self._nplurals == 1 or self.textviews.index(textview) == self._nplurals - 1:
                self.must_advance = True
                self.editing_done()
            else:
                new_index = self.textviews.index(textview) + 1
                self.textviews[new_index].grab_focus()
                self._place_cursor(new_index)
            return True
        # Automatically move to the next line if \n is entered
        if event.keyval == gtk.keysyms.n:
            buf = textview.get_buffer()
            cursor_position = buf.get_iter_at_offset(buf.props.cursor_position)
            one_back = buf.get_iter_at_offset(buf.props.cursor_position-1)
            previous = buf.get_text(one_back, cursor_position)
            if previous == '\\':
                buf.insert_at_cursor('n\n')
                self.recent_textview.place_cursor_onscreen()
            else:
                # Just a normal 'n' - nothing special
                buf.insert_at_cursor('n')
            # We have to return true, otherwise another 'n' will be inserted
            return True
        return False

    def _on_source_scroll(self, _textview, _step_size, _count, _extend_selection):
        #XXX scroll the source???
        return True

    def _on_insert_at_cursor(self, _textview, _string):
        return True

    def _on_copy_original(self, _widget):
        for buf in self.buffers:
            buf.set_text(markup.escape(self._unit.source))
            self._place_cursor()
        return True
