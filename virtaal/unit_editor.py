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
from virtaal import undo_buffer

import re
import logging

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
import pan_app
from pan_app import _
import widgets.label_expander as label_expander
from support.simplegeneric import generic
from support.partial import post, compose

def properties_generator(widget, *prop_list):
    for prop in prop_list:
        try:
            yield (prop, widget.get_property(prop))
        except TypeError, e:
            try:
                yield (prop, widget.style_get_property(prop))
            except TypeError, e:
                yield (prop, getattr(widget, prop))

def properties(*spec):
    return dict(properties_generator(*spec))

def make_style():
    return {
        gtk.TextView:       properties(gtk.TextView(),       'left-margin', 'right-margin'),
        gtk.ScrolledWindow: properties(gtk.ScrolledWindow(), 'scrollbar-spacing'),
        gtk.Container:      properties(gtk.TextView(),       'border-width'),
        gtk.CheckButton:    properties(gtk.CheckButton(),    'indicator-size', 'indicator-spacing'),
        gtk.Widget:         properties(gtk.Button(),         'focus-line-width', 'focus-padding')
    }

STYLE = make_style()

def on_key_press_event(widget, event, *args):
    if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
        widget.parent.emit('key-press-event', event)
        return True
    return False

@generic
def spacing(layout):
    raise NotImplementedError()

@spacing.when_type(unit_layout.VList)
def spacing_v_list(_layout):
    return 2


@generic
def v_padding(layout):
    raise NotImplementedError()

@v_padding.when_type(unit_layout.VList)
def v_padding_v_list(_v_list):
    return 0

@v_padding.when_type(unit_layout.HList)
def v_padding_h_list(_h_list):
    return 0

@v_padding.when_type(unit_layout.TextBox)
def v_padding_text_box(text_box):
    # A TextBox in Virtaal is composed of a ScrolledWindow which contains a TextView.
    # See gtkscrolledwindow.c:gtk_scrolled_window_size_request and
    # gtktextview.c:gtk_text_view_size_request in the GTK source for the source of this
    # calculation.
    return 2*STYLE[gtk.Widget]['focus-line-width'] + 2*STYLE[gtk.Container]['border-width']

@v_padding.when_type(unit_layout.Option)
def v_padding_comment(option):
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
    # A TextBox in Virtaal is composed of a ScrolledWindow which contains a TextView.
    # See gtkscrolledwindow.c:gtk_scrolled_window_size_request and
    # gtktextview.c:gtk_text_view_size_request in the GTK source for the source of this
    # calculation.
    return STYLE[gtk.TextView]['left-margin'] + STYLE[gtk.TextView]['right-margin'] + \
           2*STYLE[gtk.Container]['border-width']

@h_padding.when_type(unit_layout.Option)
def h_padding_option(_text_box):
    # See gtkcheckbutton.c
    # requisition->width += (indicator_size + indicator_spacing * 3 + 2 * (focus_width + focus_pad));
    return STYLE[gtk.CheckButton]['indicator-size'] + STYLE[gtk.CheckButton]['indicator-spacing'] * 3 + \
           2 * (STYLE[gtk.Widget]['focus-line-width'] + STYLE[gtk.Widget]['focus-padding'])


def cache_height(h, layout, widget, width):
    layout.__height = h
    return h

def get_cached_height(layout):
    return layout.__height

@generic
def height(layout, widget, width):
    raise NotImplementedError()

def specialize_height(type):
    # Create a composite decorator which first applies the decorator post(cache_height)
    # and then the decorator height.when_type(type).
    return compose(height.when_type(type), post(cache_height))

@specialize_height(unit_layout.Layout)
def height_layout(layout, widget, width):
    return height(layout.child, widget, width / 2)

@specialize_height(unit_layout.HList)
def height_h_list(v_list, widget, width):
    item_width = (width - len(v_list.children) * (h_padding(v_list) + 1)) / len(v_list.children)
    return 2*v_padding(v_list) + max(height(child, widget, item_width) for child in v_list.children)

@specialize_height(unit_layout.VList)
def height_v_list(v_list, widget, width):
    return sum(height(child, widget, width) for child in v_list.children) + \
           v_padding(v_list) * (len(v_list.children) - 1)

def make_pango_layout(layout, text, widget, width):
    pango_layout = pango.Layout(widget.get_pango_context())
    pango_layout.set_width((width - h_padding(layout)) * pango.SCALE)
    pango_layout.set_wrap(pango.WRAP_WORD)
    pango_layout.set_text(text)
    return pango_layout

@specialize_height(unit_layout.TextBox)
def height_text_box(text_box, widget, width):
    # TODO: Look at GTK C Source to get precise height calculations
    _w, h = make_pango_layout(text_box, markup.escape(text_box.get_text()), widget, width).get_pixel_size()

    return h + v_padding(text_box)

@specialize_height(unit_layout.Comment)
def height_comment(comment, widget, width):
    # TODO: The calculations here yield incorrect results. We'll have to look at this.
    text = comment.get_text()
    if text == "":     # If we have an empty string, we squash the comment box
        return 0
    _w, h = make_pango_layout(comment, text[0], widget, width).get_pixel_size()
    return h + v_padding(comment)
    #return height_text_box(comment, widget, 100000)

@specialize_height(unit_layout.Option)
def height_option(option, widget, width):
    _w, h = make_pango_layout(option, option.label, widget, width).get_pixel_size()
    return h + v_padding(option)


@generic
def make_widget(layout):
    raise NotImplementedError()

def associate_layout_and_widget(widget_and_names, layout):
    widget, _names = widget_and_names
    layout.__widget = widget
    widget.__layout = layout
    return widget_and_names

def get_layout(widget):
    return widget.__layout

def get_widget(layout):
    return layout.__widget

def skip_enter_processing(widget_and_names, layout):
    widget, _names = widget_and_names
    widget.connect('key-press-event', on_key_press_event)
    return widget_and_names

def specialize_make_widget(type_desc):
    return compose(make_widget.when_type(type_desc),
                   post(associate_layout_and_widget),
                   post(skip_enter_processing))

@specialize_make_widget(unit_layout.Layout)
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
    #box.connect('key-press-event', on_key_press_event)
    return box, names

@specialize_make_widget(unit_layout.VList)
def make_vlist(layout):
    return fill_list(layout, gtk.VBox(v_padding(layout)))

@specialize_make_widget(unit_layout.HList)
def make_hlist(layout):
    return fill_list(layout, gtk.HBox())

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
            spell.set_language(pan_app.settings.language["contentlang"])
        except:
            import traceback
            logging.info(_("Could not initialize spell checking"))
#            print >> sys.stderr, _("Could not initialize spell checking")
#            traceback.print_exc(file=sys.stderr)
            gtkspell = None

@specialize_make_widget(unit_layout.SourceTextBox)
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

    return scrolled_window, {layout.name: scrolled_window}

@specialize_make_widget(unit_layout.TargetTextBox)
def make_target_text_box(layout):
    text_view = gtk.TextView()

    add_spell_checking(text_view, pan_app.settings.language["contentlang"])

    def get_range(buf, left_offset, right_offset):
        return buf.get_text(buf.get_iter_at_offset(left_offset),
                            buf.get_iter_at_offset(right_offset))

    def on_text_view_key_press_event(text_view, event):
        """Handle special keypresses in the textarea."""
        # Automatically move to the next line if \n is entered

        if event.keyval == gtk.keysyms.n:
            buf = text_view.get_buffer()
            if get_range(buf, buf.props.cursor_position-1, buf.props.cursor_position) == "\\":
                buf.insert_at_cursor('n\n')
                text_view.scroll_mark_onscreen(buf.get_insert())
                return True
        return False

    def on_text_view_n_press_event(text_view, event, *args):
        if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
            layout = get_layout(text_view.parent)
            if layout.next != None:
                next_text_view = get_widget(layout.next).child
                focus_text_view(next_text_view)

            else:
                #self.must_advance = True
                text_view.parent.emit('key-press-event', event)
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
    text_view.connect('key-press-event', on_text_view_key_press_event)

    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
    scrolled_window.add(text_view)

    return scrolled_window, {layout.name: scrolled_window}

@specialize_make_widget(unit_layout.Comment)
def make_comment(comment):
    text_box, names = make_source_text_box(comment)
    expander = label_expander.LabelExpander(text_box, comment.get_text)
    return expander, names

@specialize_make_widget(unit_layout.Option)
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
    return check_button, {'option-%s' % option.name: check_button}

#A regular expression to help us find a meaningful place to position the
#cursor initially.
first_word_re = re.compile("(?m)(?u)^(<[^>]+>|\\\\[nt]|[\W$^\n])*(\\b|\\Z)")

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

        for target_widget in (get_widget(s) for s in unit_layout.get_targets(get_layout(self.layout))):
            target_widget.child.get_buffer().connect("changed", self._on_modify)

        #blueprints['copy_button'].connect("activate", self._on_copy_original)
        #editor_names['copy_button'].connect("clicked", self._on_copy_original)
        #editor_names['copy_button'].set_relief(gtk.RELIEF_NONE)

        #editor_names['fuzzy_checkbox'].connect("toggled", self._on_modified)

        self.must_advance = False
        self._modified = False
        self._unit = unit
        self._widget_dict = widget_dict

        self.connect('key-press-event', self.on_key_press_event)

    def _on_modify(self, buf):
        self.emit('modified')

    def on_key_press_event(self, widget, event, *args):
        if event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter:
            self.must_advance = True
            self.editing_done()

    def do_start_editing(self, *_args):
        """Start editing."""
        focus_text_view(self._widget_dict['target-0'].child)

    def _on_focus(self, widget, _direction):
        # TODO: Check whether we do need to refocus the last edited text_view when
        #       our program gets focus after having lost it.
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

    def _on_copy_original(self, _widget):
        for buf in self.buffers:
            buf.set_text(markup.escape(self._unit.source))
            self._place_cursor()
        return True
