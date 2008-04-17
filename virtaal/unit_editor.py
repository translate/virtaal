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
import gtk

from translate.misc.multistring import multistring

import markup
import Globals
from Globals import _
import undo_buffer


#A regular expression to help us find a meaningful place to position the 
#cursor initially.
first_word_re = re.compile("(?m)(?u)^(<[^>]+>|\\\\[nt]|[\W$^\n])*(\\b|\\Z)")

def on_size_allocate(widget, allocation):
    widget.child.set_size_request(allocation.width - 2, -1)

class CellUnitView(gtk.EventBox, gtk.CellEditable):
    """Text view suitable for cell renderer use."""
    
    __gtype_name__ = "CellUnitView"
    
    __gsignals__ = {
        'modified':(gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }
        
        
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

    def do_editing_done(self, *_args):
        """End editing."""
        self.update_for_save()
        self.remove_widget()

    def do_remove_widget(self, *_args):
        """Remove widget."""
        pass

    def do_start_editing(self, *_args):
        """Start editing."""
        self.textviews[0].grab_focus()

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
    #        buf = source_view.get_buffer()
    #        buf.set_text(markup.escape(unit.source))
    #        source_view.set_editable(False)
    #        scrolledwindow = gtk.ScrolledWindow()
    #        scrolledwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
    #        scrolledwindow.add(source_view)
    #        self.vbox.pack_start(scrolledwindow, expand=True, fill=True)

        global gtkspell

        if not hasattr(unit, 'buffers'):
            unit.buffers = []
            
            for buf, undo_list in [undo_buffer.make_undo_buffer() for target in targets]:
                unit.buffers.append(buf)
                buf.undo_list = undo_list
        
        for target, buf in zip(targets, unit.buffers):
            textview = gtk.TextView(buf)
            if gtkspell:
                try:
                    spell = gtkspell.Spell(textview)
                    spell.set_language(Globals.settings.language["contentlang"])
                except:
                    import traceback
                    
                    print >> sys.stderr, _("Could not initialize spell checking")
                    traceback.print_exc(file=sys.stderr)
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

            buf = textview.get_buffer()
            undo_buffer.execute_without_signals(buf, lambda: buf.set_text(markup.escape(target)))
            buf.set_modified(False)

            buf.connect("modified-changed", self._on_modified)
            self.buffers.append(buf)
        
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
