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

import pango

import markup

class Widget(object):
    def __init__(self, name):
        self.name = name
    
    def height(self, width):
        raise NotImplementedError()
    
class List(Widget):
    def __init__(self, name):
        super(List, self).__init__(name)
        
        self.hpadding = 2
        self.vpadding = 2
        self.children = []
    
    def total_padding_space(self, padding):
        return (len(self.children) + 1) * padding
    
    def add(self, widget):
        self.children.append(widget)
        
class VList(List):
    def height(self, width):
        item_width = (width - self.total_padding_space(self.hpadding)) / len(self.children)
        return 2*self.vpadding + max(child.height(item_width) for child in self.children)
            
class HList(List):
    def height(self, width):
        return sum(child.height(width - 2*self.hpadding) for child in self.children) + self.total_padding_space(self.vpadding)
        
class TextBox(Widget):
    def __init__(self, name, widget, get_text):
        super(TextBox, self).__init__(name)
        
        self.get_text = get_text
        self.layout = pango.Layout(widget.get_pango_context())
        self.layout.set_wrap(pango.WRAP_WORD_CHAR)

    def height(self, width):
        self.layout.set_width(width * pango.SCALE)
        self.layout.set_markup(markup.markuptext(self.get_text()))
        __, height = self.layout.get_pixel_size()
        
        return height

def get_sources(unit):
    if unit.hasplural():
        return unit.source.strings
    else:
        return [unit.source]
    
def get_targets(unit, nplurals):
    if unit.hasplural():
        targets = nplurals * [u""]
        targets[:len(unit.target.strings)] = unit.target.strings
        return targets
    else:
        return [unit.target]

def get_source_and_target(unit, nplurals):
    return get_sources(unit), get_targets(unit, nplurals)

def build_layout(widget, unit, nplurals):
    """Construct a blueprint which can be used to build editor widgets
    or to compute the height required to display editor widgets; this
    latter operation is required by the TreeView.
    
    @param widget: Any valid GTK widget. This abstraction leak is required 
                   because the computation of Pango layout sizes requires
                   a proper widget to be passed to the Pango routines.
    @param unit: A translation unit used by the translate toolkit.
    @param nplurals: The number of plurals in the 
    """
    
    source_list = VList('sources')
    for i in xrange(len(get_sources(unit))):
        source_list.children.append(TextBox('source-%d' % i, widget, lambda: unicode(get_sources(unit)[i])))
        
    target_list = VList('targets')
    for i in xrange(len(get_targets(unit, nplurals))):
        target_list.children.append(TextBox('target-%d' % i, widget, lambda: unicode(get_targets(unit, nplurals)[i])))
                                    
    main_list = VList('main_list')
    main_list.children.append(source_list)
    main_list.children.append(target_list)
    
    return main_list

def get_blueprints(unit, widget):
    """Return a layout description used to construct UnitEditors
    
    @param unit: A translation unit (from the translate toolkit)
    @param widget: A valid GTK widget. This should always be a 
                   gtk.TreeView.
    """
    if not hasattr(unit, '__blueprints'):
        # TODO: We should not obtain the number of plurals from the TreeView
        # widget. At some point, nplurals won't be stored in the TreeView anymore
        unit.__blueprints = build_layout(widget, unit, widget._nplurals)
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

