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

import logging

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from virtaal.views import markup, rendering


class TMWindow(Gtk.Window):
    """Constructs the main TM window and all its children."""

    MAX_HEIGHT = 300

    # INITIALIZERS #
    def __init__(self, view):
        super(TMWindow, self).__init__(Gtk.WindowType.POPUP)
        self.view = view

        # set_has_frame is the method of Gtk.Enter, not found on Gtk.Window
        # self.set_has_frame(True)

        self._build_gui()

    def _build_gui(self):
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled_window.set_shadow_type(Gtk.ShadowType.IN)

        self.treeview = self._create_treeview()

        self.scrolled_window.add(self.treeview)
        self.add(self.scrolled_window)

    def _create_treeview(self):
        self.liststore = Gtk.ListStore(GObject.TYPE_PYOBJECT, GObject.TYPE_STRING)
        treeview = Gtk.TreeView(model=self.liststore)
        treeview.set_rules_hint(False)
        treeview.set_headers_visible(False)

        self.perc_renderer = Gtk.CellRendererProgress()
        self.match_renderer = TMMatchRenderer(self.view)
        self.tm_source_renderer = TMSourceColRenderer(self.view)

        # l10n: match quality column label
        self.tvc_perc = Gtk.TreeViewColumn(_('%'), self.perc_renderer)
        self.tvc_perc.set_cell_data_func(self.perc_renderer, self._percent_data_func)
        self.tvc_match = Gtk.TreeViewColumn(_('Matches'), self.match_renderer, matchdata=0)
        self.tvc_match.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.tvc_tm_source = Gtk.TreeViewColumn(_('TM Source'), self.tm_source_renderer, matchdata=0)
        self.tvc_tm_source.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)

        treeview.append_column(self.tvc_perc)
        treeview.append_column(self.tvc_match)
        treeview.append_column(self.tvc_tm_source)
        treeview.set_tooltip_column(1)

        return treeview

    # METHODS #
    def rows_height(self):
        height = 0
        itr = self.liststore.get_iter_first()
        vert_sep = self.treeview.style_get_property('vertical-separator')
        while itr and self.liststore.iter_is_valid(itr):
            path = self.liststore.get_path(itr)
            height += self.treeview.get_cell_area(path, self.tvc_match).height + vert_sep
            itr = self.liststore.iter_next(itr)
        # This seems necessary on some themes, but on others (like wimp and the
        # large inverse theme of GNOME, it causes the scrollbar to appear.
        #if height:
        #    height -= vert_sep

        return height

    def update_geometry(self, widget):
        """Move this window to right below the given widget so that C{widget}'s
            bottom left corner and this window's top left corner line up."""
        if not self.props.visible:
            return

        widget_alloc = widget.get_parent().get_allocation()
        gdkwin = widget.get_window(Gtk.TextWindowType.WIDGET)
        if gdkwin is None:
            return
        vscrollbar = self.scrolled_window.get_vscrollbar()
        scrollbar_width = vscrollbar.props.visible and vscrollbar.get_allocation().width + 1 or 0

        origin = gdkwin.get_origin()
        x, y = origin.x, origin.y

        if widget.get_direction() == Gtk.TextDirection.LTR:
            x -= self.tvc_perc.get_width()
        else:
            x -= self.tvc_tm_source.get_width() + scrollbar_width
        y += widget_alloc.height + 2

        tm_source_width = self.tvc_tm_source.get_width()
        if tm_source_width > 100:
            # Sometimes this column is still way too wide after a reconfigure.
            # See bug 1809 for more detail.
            tm_source_width = self.tvc_perc.get_width()
        width = widget_alloc.width + self.tvc_perc.get_width() + tm_source_width + scrollbar_width
        height = min(self.rows_height(), self.MAX_HEIGHT) + 4
        # TODO: Replace the hard-coded value above with a query to the theme. It represents the width of the shadow of self.scrolled_window

        #logging.debug('TMWindow.update_geometry(%dx%d +%d+%d)' % (width, height, x, y))
        self.resize(width, height)
        self.scrolled_window.set_size_request(width, height)
        window = self.get_window()
        window.move_resize(0,0, width,height)
        window.get_toplevel().move_resize(x,y, width,height)


    # EVENT HANLDERS #
    def _percent_data_func(self, column, cell_renderer, tree_model, iter, user_data):
        match_data = tree_model.get_value(iter, 0)
        if match_data.get('quality', None) is not None:
            quality = int(match_data['quality'])
            cell_renderer.set_property('value', quality)
            #l10n: This message allows you to customize the appearance of the match percentage. Most languages can probably leave it unchanged.
            cell_renderer.set_property('text', _("%(match_quality)s%%") % \
                    {"match_quality": quality})
            return
        elif Gtk.gtk_version < (2, 16, 0):
            # Rendering bug with some older versions of GTK if a progress is at
            # 0%. GNOME bug 567253.
            cell_renderer.set_property('value', 3)
        else:
            cell_renderer.set_property('value', 0)
        #l10n: This indicates a suggestion from machine translation. It is displayed instead of the match percentage.
        cell_renderer.set_property('text', _(u"?"))


class TMSourceColRenderer(Gtk.CellRenderer):
    """
    Renders the TM source for the row.
    """

    __gtype_name__ = "TMSourceColRenderer"
    __gproperties__ = {
        "matchdata": (
            GObject.TYPE_PYOBJECT,
            "The match data.",
            "The match data that this renderer is currently handling",
            GObject.PARAM_READWRITE
        ),
    }

    YPAD = 2

    # INITIALIZERS #
    def __init__(self, view):
        super(TMSourceColRenderer, self).__init__()

        self.view = view
        self.matchdata = None


    # INTERFACE METHODS #
    def on_get_size(self, widget, cell_area):
        if 'tmsource' not in self.matchdata:
            return 0, 0, 0, 0

        label = Gtk.Label()
        label.set_markup(u'<small>%s</small>' % self.matchdata['tmsource'])
        label.get_pango_context().set_base_gravity(Pango.Gravity.AUTO)
        label.set_angle(270)
        size = label.size_request()
        return 0, 0, size[0], size[1] + self.YPAD*2

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def on_render(self, window, widget, _background_area, cell_area, _expose_area, _flags):
        if 'tmsource' not in self.matchdata:
            return
        x_offset = 0
        y_offset = 0

        x = cell_area.x + x_offset
        y = cell_area.y + y_offset + self.YPAD

        label = Gtk.Label()
        label.set_markup(u'<small>%s</small>' % self.matchdata['tmsource'])
        label.get_pango_context().set_base_dir(Pango.Direction.TTB_LTR)
        if widget.get_direction() == Gtk.TextDirection.RTL:
            label.set_angle(90)
        else:
            label.set_angle(270)
        label.set_alignment(0.5, 0.5)
        widget.get_style().paint_layout(window, Gtk.StateType.NORMAL, False,
                                        cell_area, widget, '', x, y, label.get_layout())


class TMMatchRenderer(Gtk.CellRenderer):
    """
    Renders translation memory matches.

    This class was adapted from C{virtaal.views.widgets.storecellrenderer.StoreCellRenderer}.
    """

    __gtype_name__ = 'TMMatchRenderer'
    __gproperties__ = {
        "matchdata": (
            GObject.TYPE_PYOBJECT,
            "The match data.",
            "The match data that this renderer is currently handling",
            GObject.PARAM_READWRITE
        ),
    }

    BOX_MARGIN = 3
    """The number of pixels between where the source box is drawn and where the
        text layout begins."""
    LINE_SEPARATION = 10
    """The number of pixels between source and target in a single row."""
    ROW_PADDING = 6
    """The number of pixels between rows."""

    # INITIALIZERS #
    def __init__(self, view):
        super(TMMatchRenderer, self).__init__()

        self.view = view
        self.layout = None
        self.matchdata = None


    # INTERFACE METHODS #
    def do_get_size(self, widget, cell_area):
        width = self.view.get_target_width() - self.BOX_MARGIN
        height = self._compute_cell_height(widget, width)
        height = min(height, 600)
        #print 'do_get_size() (w, h):', width, height

        x_offset = 0
        y_offset = self.ROW_PADDING / 2
        return x_offset, y_offset, width, height

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_render(self, window, widget, _background_area, cell_area, _flags):
        x_offset = 0
        y_offset = self.BOX_MARGIN
        width = cell_area.width
        height = self._compute_cell_height(widget, width)
        style_context = widget.get_style_context()

        x = cell_area.x + x_offset
        if not self.source_layout:
            # We do less for MT results
            target_y = cell_area.y
            # x + source_dx?
            Gtk.render_layout(style_context, window, x, target_y, self.target_layout)
            return

        source_height = self.source_layout.get_pixel_size()[1]
        source_y = cell_area.y + y_offset
        target_y = cell_area.y + y_offset + source_height + self.LINE_SEPARATION

        source_dx = target_dx = self.BOX_MARGIN

        style_context.save()
        style_context.add_class(Gtk.STYLE_CLASS_TROUGH)
        Gtk.render_background(style_context, window, x, source_y - self.BOX_MARGIN, width, source_height + (self.LINE_SEPARATION/2))
        Gtk.render_layout(style_context, window, x + source_dx, source_y, self.source_layout)
        Gtk.render_layout(style_context, window, x + target_dx, target_y, self.target_layout)
        style_context.restore()

    # METHODS #
    def _compute_cell_height(self, widget, width):
        srclang = self.view.controller.main_controller.lang_controller.source_lang.code
        tgtlang = self.view.controller.main_controller.lang_controller.target_lang.code

        self.target_layout = self._get_pango_layout(
            widget, self.matchdata['target'], width - (2*self.BOX_MARGIN),
            rendering.get_target_font_description()
        )
        self.target_layout.get_context().set_language(rendering.get_language(tgtlang))

        if self.matchdata.get('quality', 0) == 0 and \
                self.matchdata['source'] == self.matchdata['query_str']:
            # We do less for MT results
            self.source_layout = None
            height = self.target_layout.get_pixel_size()[1]
            return height + self.ROW_PADDING

        else:
            self.source_layout = self._get_pango_layout(
                widget, self.matchdata['source'], width - (2*self.BOX_MARGIN),
                rendering.get_source_font_description(),
                self.matchdata['query_str']
            )
            self.source_layout.get_context().set_language(rendering.get_language(srclang))

            height = self.source_layout.get_pixel_size()[1] + self.target_layout.get_pixel_size()[1]
            return height + self.LINE_SEPARATION + self.ROW_PADDING

    def _get_pango_layout(self, widget, text, width, font_description, diff_text=u""):
        '''Gets the Pango layout used in the cell in a TreeView widget.'''
        # We can't use widget.get_pango_context() because we'll end up
        # overwriting the language and font settings if we don't have a
        # new one
        layout = Pango.Layout(widget.create_pango_context())
        layout.set_font_description(font_description)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_width(width * Pango.SCALE)
        #XXX - plurals?
        layout.set_markup(markup.markuptext(text, diff_text=diff_text))
        # This makes no sense, but has the desired effect to align things correctly for
        # both LTR and RTL languages:
        if widget.get_direction() == Gtk.TextDirection.RTL:
            layout.set_alignment(Pango.Alignment.RIGHT)
        return layout
