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

from support.simplegeneric import generic
from support.partial import partial
from pan_app import _

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
    return [Option('option-fuzzy', _('F_uzzy'), lambda: unit.isfuzzy(), lambda value: unit.markfuzzy())]

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

    return Layout('layout',
                  VList('main_list', list(chain(
                        [Comment('programmer',
                                 partial(unit.getnotes, 'programmer'))],
                        sources,
                        [Comment('context', unit.getcontext)],
                        targets,
                        [Comment('translator',
                                 partial(unit.getnotes, 'translator'))],
                        get_options(unit)))))

def get_blueprints(unit, nplurals):
    """Return a layout description used to construct UnitEditors

    @param unit: A translation unit (from the translate toolkit)
    """
    if not hasattr(unit, '__blueprints'):
        unit.__blueprints = build_layout(unit, nplurals)
    return unit.__blueprints




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





#        if developer_comments:
#            frame = gtk.Frame(_("Developer comments"))
#            vbox.pack_start(frame)
#            frame.set_border_width(2)
#            frame.set_label_align(1.0, 0.5)
#            frame.connect('size-allocate', on_size_allocate)
#            label = gtk.Label(developer_comments)
#            frame.add(label)
#            label.set_alignment(xalign=0.0, yalign=0.0)
#            label.set_line_wrap(True)
#
#        if translator_comments:
#            frame = gtk.Frame(_("Translator comments"))
#            vbox.pack_end(frame)
#            frame.set_border_width(2)
#            frame.set_label_align(1.0, 0.5)
#            frame.connect('size-allocate', on_size_allocate)
#            label = gtk.Label(translator_comments)
#            frame.add(label)
#            label.set_alignment(xalign=0.0, yalign=0.0)
#            label.set_line_wrap(True)

