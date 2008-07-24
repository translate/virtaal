#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
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

__all__ = ['build_layout', 'get_targets']

import logging
import re

import gtk
try:
    import gtkspell
except ImportError, e:
    gtkspell = None

import pan_app
from pan_app import _
from support.partial import partial
import markup
import undo_buffer
from widgets import label_expander, util

def get_targets(widget):
    def add_targets_to_list(lst):
        def do(widget):
            if '_is_target' in widget.__dict__:
                lst.append(widget)
        return do
  
    result = []
    util.forall_widgets(add_targets_to_list(result), widget)
    return result

#A regular expression to help us find a meaningful place to position the
#cursor initially.
first_word_re = re.compile("(?m)(?u)^(<[^>]+>|\\\\[nt]|[\W$^\n])*(\\b|\\Z)")

def focus_text_view(text_view):
    text_view.grab_focus()

    buf = text_view.get_buffer()
    text = buf.get_text(buf.get_start_iter(), buf.get_end_iter())

    translation_start = first_word_re.match(text).span()[1]
    buf.place_cursor(buf.get_iter_at_offset(translation_start))

################################################################################

def add_events(widget):
    def on_key_press_event(widget, event, *_args):
        if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
            widget.parent.emit('key-press-event', event)
            return True
        return False

    # Skip Enter key processing
    widget.connect('key-press-event', on_key_press_event)
    return widget

def layout(child):
    def make():
        table = gtk.Table(rows=1, columns=4, homogeneous=True)
        table.attach(child(), 1, 3, 0, 1, xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.FILL)
        return add_events(table)
    return make

def vlist(*children):
    def make():
        box = gtk.VBox()
        for child in children:
            box.pack_start(child(), fill=True, expand=False)
        return add_events(box)
    return make

def add_spell_checking(text_view, language):
    global gtkspell
    if gtkspell:
        try:
            spell = gtkspell.Spell(text_view)
            spell.set_language(language)
        except:
            logging.info(_("Could not initialize spell checking"))
            gtkspell = None

def make_scrolled_text_view(get_text, editable, scroll_vertical, language):
    text_view = gtk.TextView()

    text_view.get_buffer().set_text(markup.escape(get_text()))
    text_view.set_editable(scroll_vertical)
    text_view.set_wrap_mode(gtk.WRAP_WORD)
    text_view.set_border_window_size(gtk.TEXT_WINDOW_TOP, 1)
    add_spell_checking(text_view, pan_app.settings.language[language])

    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_policy(gtk.POLICY_NEVER, scroll_vertical)
    scrolled_window.add(text_view)
    
    return text_view, add_events(scrolled_window)

def source_text_box(get_text, set_text):
    def make():
        _text_view, scrolled_window = make_scrolled_text_view(get_text, False, gtk.POLICY_NEVER, "sourcelang")
        return scrolled_window
    return make
  
def target_text_box(get_text, set_text):
    def make():            
        def get_range(buf, left_offset, right_offset):
            return buf.get_text(buf.get_iter_at_offset(left_offset),
                                buf.get_iter_at_offset(right_offset))
    
        def on_text_view_n_press_event(text_view, event):
            """Handle special keypresses in the textarea."""
            # Automatically move to the next line if \n is entered
    
            if event.keyval == gtk.keysyms.n:
                buf = text_view.get_buffer()
                if get_range(buf, buf.props.cursor_position-1, buf.props.cursor_position) == "\\":
                    buf.insert_at_cursor('n\n')
                    text_view.scroll_mark_onscreen(buf.get_insert())
                    return True
            return False
    
        def on_change(buf):
            set_text(markup.unescape(buf.get_text(buf.get_start_iter(), buf.get_end_iter())))
    
        text_view, scrolled_window = make_scrolled_text_view(get_text, True, gtk.POLICY_AUTOMATIC, "contentlang")
        text_view.connect('key-press-event', on_text_view_n_press_event)
        text_view._is_target = True

        buf = undo_buffer.add_undo_to_buffer(text_view.get_buffer())
        undo_buffer.execute_without_signals(buf, lambda: buf.set_text(markup.escape(get_text())))
        buf.connect('changed', on_change)

        return scrolled_window
    return make

def connect_target_text_views(child):
    def make():
        def target_key_press_event(text_view, event, next_text_view):
            if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
                focus_text_view(next_text_view)
                return True
            return False
    
        def end_target_key_press_event(text_view, event, *_args):
            if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
                text_view.parent.emit('key-press-event', event)
                return True
            return False
    
        widget = child()
        targets = get_targets(widget)
        for target, next_target in zip(targets, targets[1:]):
            target.connect('key-press-event', target_key_press_event, next_target)
        targets[-1].connect('key-press-event', end_target_key_press_event)
        return widget
    return make

def comment(get_text, set_text=lambda value: None):
    def make():
        text_box = source_text_box(get_text, set_text)()
        return label_expander.LabelExpander(text_box, get_text)
    return make
  
def option(label, get_option, set_option):
    def make():
        def on_toggled(widget, *_args):
            if widget.get_active():
                set_option(True)
            else:
                set_option(False)
    
        check_button = gtk.CheckButton(label=label)
        check_button.connect('toggled', on_toggled)
        check_button.set_active(get_option())
        return check_button
    return make

################################################################################

def build_layout(unit, nplurals):
    """Construct a blueprint which can be used to build editor widgets
    or to compute the height required to display editor widgets; this
    latter operation is required by the TreeView.

    @param unit: A translation unit used by the translate toolkit.
    @param nplurals: The number of plurals in the
    """

    def get(multistring, unit, i):
        if unit.hasplural():
            return multistring.strings[i]
        elif i == 0:
            return multistring
        else:
            raise IndexError()

    def get_source(unit, index):
        return get(unit.source, unit, index)
    
    def get_target(unit, nplurals, index):
        if unit.hasplural() and nplurals != len(unit.target.strings):
            targets = nplurals * [u""]
            targets[:len(unit.target.strings)] = unit.target.strings
            unit.target = targets
        return get(unit.target, unit, index)
    
    def set(unit, attr, index, value):
        if unit.hasplural():
            str_list = list(getattr(unit, attr).strings)
            str_list[index] = value
            setattr(unit, attr, str_list)
        elif index == 0:
            setattr(unit, attr, value)
        else:
            raise IndexError()
    
    def set_source(unit, index, value):
        set(unit, 'source', index, value)
    
    def set_target(unit, index, value):
        set(unit, 'target', index, value)

    def num_sources(unit):
        if unit.hasplural():
            return len(unit.source.strings)
        return 1
    
    def num_targets(unit, nplurals):
        if unit.hasplural():
            return nplurals
        return 1

    maker = layout(vlist(
                 comment(partial(unit.getnotes, 'programmer')),
                 vlist(*(source_text_box(partial(get_source, unit, i), 
                                         partial(set_source, unit, i))
                         for i in xrange(num_sources(unit)))),
                 comment(unit.getcontext),
                 connect_target_text_views(
                    vlist(*(target_text_box(partial(get_target, unit, nplurals, i), 
                                            partial(set_target, unit, i))
                            for i in xrange(num_targets(unit, nplurals))))),
                 comment(partial(unit.getnotes, 'translator')),
                 option(_('F_uzzy'), unit.isfuzzy,
                                     partial(unit.markfuzzy, value))))
    return maker()
