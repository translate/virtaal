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

from itertools import chain
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
from support.simplegeneric import generic
import markup
import undo_buffer
from widgets import label_expander 

@generic
def get_children(widget):
    return []
  
@get_children.when_type(gtk.Container)
def get_children_container(widget):
    return widget.get_children()

def forall_widgets(f, widget):
    f(widget)

    for child in get_children(widget):
        forall_widgets(f, child)

def get_targets(widget):
    def add_targets_to_list(lst):
        def do(widget):
            if '_is_target' in widget.__dict__:
                lst.append(widget)
        return do
  
    result = []
    forall_widgets(add_targets_to_list(result), widget)
    return result

class Widget(object):
    def __init__(self, name):
        self.name = name
        self.parent = None
        self.children = []

class Layout(Widget):
    def __init__(self, name, child):
        super(Layout, self).__init__(name)
        self.child = child
        self.children.append(self.child)
        self.child.parent = self

class List(Widget):
    def __init__(self, name, children=None):
        super(List, self).__init__(name)

        if children != None:
            self.children = children

        for child in self.children:
            child.parent = self

    def add(self, widget):
        self.children.append(widget)

class VList(List):
    pass

class HList(List):
    pass

class TextBox(Widget):
    def __init__(self, name, get_text, set_text, editable):
        super(TextBox, self).__init__(name)
        self.get_text = get_text
        self.set_text = set_text
        self.next     = None
        self.editable = editable

class SourceTextBox(TextBox):
    def __init__(self, name, get_text, set_text):
        super(SourceTextBox, self).__init__(name, get_text, set_text, False)

class TargetTextBox(TextBox):
    def __init__(self, name, get_text, set_text):
        super(TargetTextBox, self).__init__(name, get_text, set_text, True)

class Comment(TextBox):
    def __init__(self, name, get_text, set_text=lambda value: None):
        super(Comment, self).__init__(name, get_text, set_text, False)

class Option(Widget):
    def __init__(self, name, label, get_option, set_option):
        super(Option, self).__init__(name)
        self.label = label
        self.get_option = get_option
        self.set_option = set_option

def on_key_press_event(widget, event, *_args):
    if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
        widget.parent.emit('key-press-event', event)
        return True
    return False

@generic
def make_widget(layout):
    raise NotImplementedError()

def post_make_widget(widget, names, layout):
    layout.__widget = widget
    widget.__layout = layout
    # Skip Enter key processing
    widget.connect('key-press-event', on_key_press_event)
    return widget, names

def get_layout(widget):
    return widget.__layout

def get_widget(layout):
    return layout.__widget

@make_widget.when_type(Layout)
def make_layout(layout):
    table = gtk.Table(rows=1, columns=4, homogeneous=True)
    names = {layout.name: table}
    child, child_names = make_widget(layout.child)
    table.attach(child, 1, 3, 0, 1, xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.FILL)
    names.update(child_names)

    return post_make_widget(table, names, layout)

def fill_list(lst, box):
    names = {lst.name: box}
    for child in lst.children:
        child_widget, child_names = make_widget(child)
        box.pack_start(child_widget, fill=True, expand=False)
        names.update(child_names)
    #box.connect('key-press-event', on_key_press_event)
    return box, names

@make_widget.when_type(VList)
def make_vlist(layout):
    box, names = fill_list(layout, gtk.VBox())
    return post_make_widget(box, names, layout)

@make_widget.when_type(HList)
def make_hlist(layout):
    box, names = fill_list(layout, gtk.HBox())
    return post_make_widget(box, names, layout)

#A regular expression to help us find a meaningful place to position the
#cursor initially.
first_word_re = re.compile("(?m)(?u)^(<[^>]+>|\\\\[nt]|[\W$^\n])*(\\b|\\Z)")

def focus_text_view(text_view):
    text_view.grab_focus()

    buf = text_view.get_buffer()
    text = buf.get_text(buf.get_start_iter(), buf.get_end_iter())

    translation_start = first_word_re.match(text).span()[1]
    buf.place_cursor(buf.get_iter_at_offset(translation_start))

def add_spell_checking(text_view, language):
    global gtkspell
    if gtkspell:
        try:
            spell = gtkspell.Spell(text_view)
            spell.set_language(language)
        except:
            logging.info(_("Could not initialize spell checking"))
            gtkspell = None

@make_widget.when_type(SourceTextBox)
def make_source_text_box(layout):
    text_view = gtk.TextView()

    add_spell_checking(text_view, pan_app.settings.language["sourcelang"])

    text_view.get_buffer().set_text(markup.escape(layout.get_text()))
    text_view.set_editable(layout.editable)
    text_view.set_wrap_mode(gtk.WRAP_WORD)
    text_view.set_border_window_size(gtk.TEXT_WINDOW_TOP, 1)

    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)
    scrolled_window.add(text_view)

    return post_make_widget(scrolled_window, {layout.name: scrolled_window}, layout)

@make_widget.when_type(TargetTextBox)
def make_target_text_box(layout):
    text_view = gtk.TextView()
    text_view._is_target = True

    add_spell_checking(text_view, pan_app.settings.language["contentlang"])

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
        layout.set_text(markup.unescape(buf.get_text(buf.get_start_iter(), buf.get_end_iter())))

    buf = undo_buffer.add_undo_to_buffer(text_view.get_buffer())
    undo_buffer.execute_without_signals(buf, lambda: buf.set_text(markup.escape(layout.get_text())))
    buf.connect('changed', on_change)

    text_view.set_editable(layout.editable)
    text_view.set_wrap_mode(gtk.WRAP_WORD)
    text_view.set_border_window_size(gtk.TEXT_WINDOW_TOP, 1)
    text_view.connect('key-press-event', on_text_view_n_press_event)

    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
    scrolled_window.add(text_view)

    return post_make_widget(scrolled_window, {layout.name: scrolled_window}, layout)

@make_widget.when_type(Comment)
def make_comment(comment):
    text_box, names = make_source_text_box(comment)
    expander = label_expander.LabelExpander(text_box, comment.get_text)
    return post_make_widget(expander, names, comment)

@make_widget.when_type(Option)
def make_option(option):
    def on_toggled(widget, *_args):
        if widget.get_active():
            option.set_option(True)
        else:
            option.set_option(False)

    check_button = gtk.CheckButton(label=option.label)
    check_button.connect('toggled', on_toggled)
    if option.get_option():
        check_button.set_active(True)
    return post_make_widget(check_button, {'option-%s' % option.name: check_button}, option)

def get_source(unit, index):
    if unit.hasplural():
        return unit.source.strings[index]
    elif index == 0:
        return unit.source
    else:
        raise IndexError()

def get_target(unit, nplurals, index):
    if unit.hasplural():
        if nplurals != len(unit.target.strings):
            targets = nplurals * [u""]
            targets[:len(unit.target.strings)] = unit.target.strings
            unit.target = targets

        return unit.target.strings[index]
    elif index == 0:
        return unit.target
    else:
        raise IndexError()

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
    else:
        return 1

def num_targets(unit, nplurals):
    if unit.hasplural():
        return nplurals
    else:
        return 1

def get_options(unit):
    return [Option('option-fuzzy', _('F_uzzy'), lambda: unit.isfuzzy(), lambda value: unit.markfuzzy(value))]

def connect_target_text_views(widget):
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

    targets = get_targets(widget)
    for target, next_target in zip(targets, targets[1:]):
        target.connect('key-press-event', target_key_press_event, next_target)
    targets[-1].connect('key-press-event', end_target_key_press_event)

def build_layout(unit, nplurals):
    """Construct a blueprint which can be used to build editor widgets
    or to compute the height required to display editor widgets; this
    latter operation is required by the TreeView.

    @param unit: A translation unit used by the translate toolkit.
    @param nplurals: The number of plurals in the
    """

    sources = [SourceTextBox('source-%d' % i,
                       partial(get_source, unit, i),
                       partial(set_source, unit, i))
               for i in xrange(num_sources(unit))]

    targets = [TargetTextBox('target-%d' % i,
                       partial(get_target, unit, nplurals, i),
                       partial(set_target, unit, i))
               for i in xrange(num_targets(unit, nplurals))]

    all_text = list(chain(sources, targets))
    for first, second in zip(all_text, all_text[1:]):
        first.next = second

    layout = Layout('layout',
                  VList('main_list', list(chain(
                        [Comment('programmer',
                                 partial(unit.getnotes, 'programmer'))],
                        sources,
                        [Comment('context', unit.getcontext)],
                        targets,
                        [Comment('translator',
                                 partial(unit.getnotes, 'translator'))],
                        get_options(unit)))))

    widget = make_widget(layout)[0]
    connect_target_text_views(widget)
    return widget


