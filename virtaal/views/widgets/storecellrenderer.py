#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2010 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import gtk
import gobject
import pango

from translate.lang import factory

from virtaal.common import pan_app
from virtaal.support.simplegeneric import generic
from virtaal.views import markup, rendering
from virtaal.views.theme import current_theme


@generic
def compute_optimal_height(widget, width):
    raise NotImplementedError()

@compute_optimal_height.when_type(gtk.Widget)
def gtk_widget_compute_optimal_height(widget, width):
    pass

@compute_optimal_height.when_type(gtk.Container)
def gtk_container_compute_optimal_height(widget, width):
    if not widget.props.visible:
        return
    for child in widget.get_children():
        compute_optimal_height(child, width)

@compute_optimal_height.when_type(gtk.Table)
def gtk_table_compute_optimal_height(widget, width):
    for child in widget.get_children():
        # width / 2 because we use half of the available width
        compute_optimal_height(child, width / 2)

def make_pango_layout(widget, text, width):
    pango_layout = pango.Layout(widget.get_pango_context())
    pango_layout.set_width(width * pango.SCALE)
    pango_layout.set_wrap(pango.WRAP_WORD_CHAR)
    pango_layout.set_text(text or u"")
    return pango_layout

@compute_optimal_height.when_type(gtk.TextView)
def gtk_textview_compute_optimal_height(widget, width):
    if not widget.props.visible:
        return
    buf = widget.get_buffer()
    # For border calculations, see gtktextview.c:gtk_text_view_size_request in the GTK source
    border = 2 * widget.border_width - 2 * widget.parent.border_width
    if widget.style_get_property("interior-focus"):
        border += 2 * widget.style_get_property("focus-line-width")

    buftext = buf.get_text(buf.get_start_iter(), buf.get_end_iter())
    # A good way to test height estimation is to use it for all units and
    # compare the reserved space to the actual space needed to display a unit.
    # To use height estimation for all units (not just empty units), use:
    #if True:
    if not buftext:
        text = getattr(widget, '_source_text', u"")
        if text:
            lang = factory.getlanguage(pan_app.settings.language["targetlang"])
            buftext = lang.alter_length(text)
            buftext = markup.escape(buftext)

    _w, h = make_pango_layout(widget, buftext, width - border).get_pixel_size()
    if h == 0:
        # No idea why this bug happens, but it often happens for the first unit
        # directly after the file is opened. For now we try to guess a more
        # useful default than 0. This should look much better than 0, at least.
        h = 28
    parent = widget.parent
    if isinstance(parent, gtk.ScrolledWindow) and parent.get_shadow_type() != gtk.SHADOW_NONE:
        border += 2 * parent.rc_get_style().ythickness
    widget.parent.set_size_request(-1, h + border)

@compute_optimal_height.when_type(gtk.Label)
def gtk_label_compute_optimal_height(widget, width):
    if widget.get_text().strip() == "":
        widget.set_size_request(width, 0)
    else:
        _w, h = make_pango_layout(widget, widget.get_label(), width).get_pixel_size()
        widget.set_size_request(width, h)


class StoreCellRenderer(gtk.GenericCellRenderer):
    """
    Cell renderer for a unit based on the C{UnitRenderer} class from Virtaal's
    pre-MVC days.
    """

    __gtype_name__ = "StoreCellRenderer"

    __gproperties__ = {
        "unit": (
            object,
            "The unit",
            "The unit that this renderer is currently handling",
            gobject.PARAM_READWRITE
        ),
        "editable": (
            bool,
            "editable",
            "A boolean indicating whether this unit is currently editable",
            False,
            gobject.PARAM_READWRITE
        ),
    }

    __gsignals__ = {
        "editing-done": (
            gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
            (gobject.TYPE_STRING, gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN)
        ),
        "modified": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }

    ROW_PADDING = 10
    """The number of pixels between rows."""

    # INITIALIZERS #
    def __init__(self, view):
        gtk.GenericCellRenderer.__init__(self)
        self.set_property('mode', gtk.CELL_RENDERER_MODE_EDITABLE)
        self.view = view
        self.__unit = None
        self.editable = False
        self._editor = None
        self.source_layout = None
        self.target_layout = None


    # ACCESSORS #
    def _get_unit(self):
        return self.__unit

    def _set_unit(self, value):
        if value.isfuzzy():
            self.props.cell_background = current_theme['fuzzy_row_bg']
            self.props.cell_background_set = True
        else:
            self.props.cell_background_set = False
        self.__unit = value

    unit = property(_get_unit, _set_unit, None, None)


    # INTERFACE METHODS #
    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_get_size(self, widget, _cell_area):
        #TODO: store last unitid and computed dimensions
        width = widget.get_toplevel().get_allocation().width - 32
        if width < -1:
            width = -1
        if self.editable:
            editor = self.view.get_unit_celleditor(self.unit)
            editor.set_size_request(width, -1)
            editor.show()
            compute_optimal_height(editor, width)
            parent_height = widget.get_allocation().height
            if parent_height < -1:
                parent_height = widget.size_request()[1]
            if parent_height > 0:
                self.check_editor_height(editor, width, parent_height)
            _width, height = editor.size_request()
            height += self.ROW_PADDING
        else:
            height = self.compute_cell_height(widget, width)
        #height = min(height, 600)
        y_offset = self.ROW_PADDING / 2
        return 0, y_offset, width, height

    def do_start_editing(self, _event, tree_view, path, _bg_area, cell_area, _flags):
        """Initialize and return the editor widget."""
        editor = self.view.get_unit_celleditor(self.unit)
        editor.set_size_request(cell_area.width, cell_area.height)
        if not getattr(self, '_editor_editing_done_id', None):
            self._editor_editing_done_id = editor.connect("editing-done", self._on_editor_done)
        if not getattr(self, '_editor_modified_id', None):
            self._editor_modified_id = editor.connect("modified", self._on_modified)
        return editor

    def on_render(self, window, widget, _background_area, cell_area, _expose_area, _flags):
        if self.editable:
            return True
        x_offset, y_offset, width, _height = self.do_get_size(widget, cell_area)
        x = cell_area.x + x_offset
        y = cell_area.y + y_offset
        source_x = x
        target_x = x
        if widget.get_direction() == gtk.TEXT_DIR_LTR:
            target_x += width/2
        else:
            source_x += (width/2) + 10
        widget.get_style().paint_layout(window, gtk.STATE_NORMAL, False,
                cell_area, widget, '', source_x, y, self.source_layout)
        widget.get_style().paint_layout(window, gtk.STATE_NORMAL, False,
                cell_area, widget, '', target_x, y, self.target_layout)


    # METHODS #
    def _get_pango_layout(self, widget, text, width, font_description):
        '''Gets the Pango layout used in the cell in a TreeView widget.'''
        # We can't use widget.get_pango_context() because we'll end up
        # overwriting the language and font settings if we don't have a
        # new one
        layout = pango.Layout(widget.create_pango_context())
        layout.set_font_description(font_description)
        layout.set_wrap(pango.WRAP_WORD_CHAR)
        layout.set_width(width * pango.SCALE)
        #XXX - plurals?
        text = text or u""
        layout.set_markup(markup.markuptext(text))
        return layout

    def compute_cell_height(self, widget, width):
        lang_controller = self.view.controller.main_controller.lang_controller
        srclang = lang_controller.source_lang.code
        tgtlang = lang_controller.target_lang.code
        self.source_layout = self._get_pango_layout(widget, self.unit.source, width / 2,
                rendering.get_source_font_description())
        self.source_layout.get_context().set_language(rendering.get_language(srclang))
        self.target_layout = self._get_pango_layout(widget, self.unit.target, width / 2,
                rendering.get_target_font_description())
        self.target_layout.get_context().set_language(rendering.get_language(tgtlang))
        # This makes no sense, but has the desired effect to align things correctly for
        # both LTR and RTL languages:
        if widget.get_direction() == gtk.TEXT_DIR_RTL:
            self.source_layout.set_alignment(pango.ALIGN_RIGHT)
            self.target_layout.set_alignment(pango.ALIGN_RIGHT)
            self.target_layout.set_auto_dir(False)
        _layout_width, source_height = self.source_layout.get_pixel_size()
        _layout_width, target_height = self.target_layout.get_pixel_size()
        return max(source_height, target_height) + self.ROW_PADDING

    def check_editor_height(self, editor, width, parentheight):
        notesheight = 0

        for note in editor._widgets['notes'].values():
            notesheight += note.size_request()[1]

        maxheight = parentheight - notesheight

        if maxheight < 0:
            return

        visible_textboxes = []
        for textbox in (editor._widgets['sources'] + editor._widgets['targets']):
            if textbox.props.visible:
                visible_textboxes.append(textbox)

        max_tb_height = maxheight / len(visible_textboxes)

        for textbox in visible_textboxes:
            if textbox.props.visible and textbox.parent.size_request()[1] > max_tb_height:
                textbox.parent.set_size_request(-1, max_tb_height)
                #logging.debug('%s.set_size_request(-1, %d)' % (textbox.parent, max_tb_height))


    # EVENT HANDLERS #
    def _on_editor_done(self, editor):
        self.emit("editing-done", editor.get_data("path"), editor.must_advance, editor.is_modified())
        return True

    def _on_modified(self, widget):
        self.emit("modified")
