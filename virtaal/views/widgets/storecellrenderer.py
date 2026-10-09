#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import functools

from gi.repository import GObject, Gtk, Pango
from translate.lang import factory

from virtaal.common import pan_app
from virtaal.views import markup, rendering
from virtaal.views.theme import current_theme, str_to_rgba, unit_style

from .storetreemodel import StoreTreeModel


@functools.singledispatch
def compute_optimal_height(widget, width):
    raise NotImplementedError()


@compute_optimal_height.register(Gtk.Widget)
def gtk_widget_compute_optimal_height(widget, width):
    pass


@compute_optimal_height.register(Gtk.Container)
def gtk_container_compute_optimal_height(widget, width):
    if not widget.props.visible:
        return
    for child in widget.get_children():
        if not child.props.visible:
            continue
        compute_optimal_height(child, width)


@compute_optimal_height.register(Gtk.Grid)
def gtk_table_compute_optimal_height(widget, width):
    for child in widget.get_children():
        if child.props.name != "vbox_middle":
            continue
        # width / 2 because we use half of the available width
        compute_optimal_height(child, width / 2)


@compute_optimal_height.register(Gtk.TextView)
def gtk_textview_compute_optimal_height(widget, width):
    if not widget.props.visible:
        return
    buf = widget.get_buffer()
    # For border calculations, see gtktextview.c:gtk_text_view_size_request in the GTK source
    border = 2 * widget.get_border_width() - 2 * widget.get_parent().get_border_width()
    if widget.style_get_property("interior-focus"):
        border += 2 * widget.style_get_property("focus-line-width")

    buftext = buf.props.text
    # A good way to test height estimation is to use it for all units and
    # compare the reserved space to the actual space needed to display a unit.
    # To use height estimation for all units (not just empty units), use:
    #if True:
    if not buftext:
        text = getattr(widget, '_source_text', "")
        if text:
            lang = factory.getlanguage(pan_app.settings.language["targetlang"])
            try:
                buftext = lang.alter_length(text)
            except TypeError:
                # A language class's length_difference() can return a
                # non-int that alter_length() then fails to slice with (#3770).
                buftext = text
            buftext = markup.escape(buftext)

    _w, h = rendering.make_pango_layout(widget, buftext, width - border).get_pixel_size()
    # Blind to embedded placeable widgets - approximate their real height too (#3536).
    for child in widget.get_children():
        # A third is small enough to avoid ballooning, large enough to
        # be mostly safe.
        h += child.get_preferred_height()[1] // 3
    if h == 0:
        # No idea why this bug happens, but it often happens for the first unit
        # directly after the file is opened. For now we try to guess a more
        # useful default than 0. This should look much better than 0, at least.
        h = 28
    parent = widget.get_parent()
    if isinstance(parent, Gtk.ScrolledWindow) and parent.get_shadow_type() != Gtk.ShadowType.NONE:
        parent_style = parent.get_style_context()
        frame_border = parent_style.get_border(parent_style.get_state())
        border += frame_border.top + frame_border.bottom
    widget.get_parent().set_size_request(-1, h + border)


@compute_optimal_height.register(Gtk.Label)
def gtk_label_compute_optimal_height(widget, width):
    if widget.get_text().strip() == "":
        widget.set_size_request(width, 0)
    else:
        _w, h = rendering.make_pango_layout(widget, widget.get_label(), width).get_pixel_size()
        widget.set_size_request(width, h)


class StoreCellRenderer(Gtk.CellRenderer):
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
            GObject.ParamFlags.READWRITE
        ),
        "editable": (
            bool,
            "editable",
            "A boolean indicating whether this unit is currently editable",
            False,
            GObject.ParamFlags.READWRITE
        ),
    }

    __gsignals__ = {
        "editing-done": (
            GObject.SignalFlags.RUN_FIRST, None,
            (GObject.TYPE_STRING, GObject.TYPE_BOOLEAN, GObject.TYPE_BOOLEAN)
        ),
        "modified": (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    ROW_PADDING = 10
    """The number of pixels between rows."""

    VIEWPORT_ROW_BUFFER = 25
    """Rows within this many positions of the visible range still get
    an exact Pango measurement - a margin against get_visible_range()
    under-reporting how many rows actually fit mid-validation."""

    # INITIALIZERS #
    def __init__(self, view):
        super().__init__()
        self.set_property('mode', Gtk.CellRendererMode.EDITABLE)
        self.view = view
        self.__unit = None
        self.editable = False
        self.source_layout = None
        self.target_layout = None
        # See do_get_size()'s own comment - a real Pango-measurement
        # cache, only ever consulted mid-resize, invalidated below on
        # any unit change so it can never leak between rows.
        self._cached_height = None
        # store identity/length -> {id(unit): index}, rebuilt only when
        # the store itself changes.
        self._index_cache = None
        # font description string -> (char_width, line_height).
        self._metrics_cache = {}


    # ACCESSORS #
    def _get_unit(self):
        return self.__unit

    def _set_unit(self, value):
        background = unit_style(value).get('background')
        if background:
            self.props.cell_background = background
            self.props.cell_background_set = True
        else:
            self.props.cell_background_set = False
        self.__unit = value
        self._cached_height = None

    unit = property(_get_unit, _set_unit, None, None)


    # INTERFACE METHODS #
    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_get_size(self, widget, _cell_area):
        width = widget.get_toplevel().get_allocation().width - 32
        if width < -1:
            width = -1
        treeview = self.view._treeview
        if self.editable:
            # compute_optimal_height() below does real Pango text-layout
            # measurement across every textview in the editor (source,
            # target, notes, ...) - genuinely expensive, and GTK calls
            # this on every size-allocate. During a live window resize
            # that's many calls per second for no visual benefit (word-
            # wrap barely changes between two nearly-identical widths) -
            # the cause of very slow, unresponsive horizontal window
            # dragging. Reuse storetreeview.py's
            # existing configure-event debounce: skip the expensive
            # recompute while a resize is still in progress, do one real
            # one once it settles (StoreTreeView._on_configure_settled
            # forces that via queue_resize()). Never skipped for a
            # genuine content edit - _set_unit() clears this on every
            # row change, and edits don't happen mid-resize.
            if treeview.is_resizing and self._cached_height is not None:
                height = self._cached_height
            else:
                editor = self.view.get_unit_celleditor(self.unit)
                editor.set_size_request(width, -1)
                editor.show()
                # fixme: this will make vbox_editor width too large
                compute_optimal_height(editor, width)
                parent_height = widget.get_allocation().height
                if parent_height < -1:
                    parent_height = widget.get_preferred_size()[1].height
                if parent_height > 0:
                    self.check_editor_height(editor, width, parent_height)
                height = editor.get_preferred_size()[1].height
                height += self.ROW_PADDING
                self._cached_height = height
        else:
            # Same reasoning as the editable branch above - real Pango
            # measurement (two fresh layouts, source and target) on
            # every size-allocate, but this branch runs for *every*
            # visible non-editable row, not just one - the bulk of the
            # real cost during a live resize, not the editable row
            # alone.
            if treeview.is_resizing and self._cached_height is not None:
                height = self._cached_height
            else:
                height = self.compute_cell_height(widget, width)
                self._cached_height = height
        # Otherwise scroll_to_cell can't centre this row near the end
        # of the file (translate/virtaal#1366).
        extra_padding = self._last_row_padding(treeview)
        height += extra_padding

        y_offset = self.ROW_PADDING / 2
        if self.editable:
            # Shift to the padded cell's own centre only once this row
            # is the active one, so it lands level with other rows.
            y_offset += extra_padding / 2
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

    def _paint_state_background_if_selected(self, cr, background_area, flags):
        """GTK only honours cell_background while a row isn't selected -
            the theme's own selection highlight otherwise unconditionally
            replaces it, hiding the state's background on exactly the rows a
            translator is most likely to have selected."""
        background = self.unit and unit_style(self.unit).get('background')
        if not background:
            return
        if not flags & Gtk.CellRendererState.SELECTED:
            return

        rgba = str_to_rgba(background)
        cr.save()
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)
        cr.rectangle(background_area.x, background_area.y, background_area.width, background_area.height)
        cr.fill()
        cr.restore()

    GAP_LINE_WIDTH = 2

    def _gap_edges(self, treeview):
        """Whether units are hidden right above and right below this row."""
        get_model = getattr(treeview, 'get_model', None)
        model = get_model() if get_model else None
        if not isinstance(model, StoreTreeModel) or model.visible_rows is None:
            return False, False
        store = self.view.controller.get_store()
        index = self._unit_index(store)
        row = self._row(treeview, store)
        if index is None or row is None:
            return False, False
        above = index > 0 and (row == 0 or model.path_to_store_index((row - 1,)) != index - 1)
        below = row == model.row_count() - 1 and index < len(store) - 1
        return above, below

    def _paint_gaps(self, cr, treeview, background_area):
        above, below = self._gap_edges(treeview)
        if not (above or below):
            return
        rgba = str_to_rgba(current_theme['context_gap'])
        cr.save()
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)
        if above:
            cr.rectangle(background_area.x, background_area.y, background_area.width, self.GAP_LINE_WIDTH)
        if below:
            bottom = background_area.y + background_area.height - self._last_row_padding(treeview)
            cr.rectangle(background_area.x, bottom - self.GAP_LINE_WIDTH, background_area.width, self.GAP_LINE_WIDTH)
        cr.fill()
        cr.restore()

    def _clear_last_row_padding(self, cr, treeview, background_area):
        """GTK fills the whole row, scroll padding too, with a styled row's
            background; the padding isn't part of the unit."""
        if not self.props.cell_background_set:
            return
        padding = self._last_row_padding(treeview)
        if not padding:
            return
        found, base = treeview.get_style_context().lookup_color('theme_base_color')
        if not found:
            return
        cr.save()
        cr.set_source_rgba(base.red, base.green, base.blue, base.alpha)
        cr.rectangle(background_area.x, background_area.y + background_area.height - padding,
                     background_area.width, padding)
        cr.fill()
        cr.restore()

    def do_render(self, window, widget, background_area, cell_area, flags):
        if background_area is not None:
            self._clear_last_row_padding(window, widget, background_area)
        if not self.editable:
            self._paint_state_background_if_selected(window, background_area, flags)
        # Also for the editable row, under its editor.
        self._paint_gaps(window, widget, background_area)
        if self.editable:
            return True

        x_offset, y_offset, width, _height = self.do_get_size(widget, cell_area)
        if self.source_layout is None or self.target_layout is None:
            # A row being painted is visible by definition, even if the
            # cached viewport do_get_size() just used said otherwise.
            # GTK still holds the estimated height, so leave the row
            # marked estimated for the revalidation to correct.
            self._compute_exact_height(widget, width)
            self.view._treeview.schedule_revalidate_visible_estimated_rows()
        x = cell_area.x + x_offset
        y = cell_area.y + y_offset
        source_x = x
        target_x = x
        if widget.get_direction() == Gtk.TextDirection.LTR:
            target_x += width/2
        else:
            source_x += (width/2) + 10
        # NORMAL regardless of selection - _paint_state_background_if_selected()
        # already handles the selected-row background, text shouldn't also
        # pick up a "selected" style on top of it.
        style_context = widget.get_style_context()
        style_context.save()
        style_context.set_state(Gtk.StateFlags.NORMAL)
        Gtk.render_layout(style_context, window, source_x, y, self.source_layout)
        Gtk.render_layout(style_context, window, target_x, y, self.target_layout)
        style_context.restore()


    # METHODS #
    def _get_pango_layout(self, widget, text, width, font_description):
        '''Gets the Pango layout used in the cell in a TreeView widget.'''
        # We can't use widget.get_pango_context() because we'll end up
        # overwriting the language and font settings if we don't have a
        # new one
        layout = Pango.Layout(widget.create_pango_context())
        layout.set_font_description(font_description)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_width(width * Pango.SCALE)
        #XXX - plurals?
        text = text or ""
        layout.set_markup(markup.markuptext(text))
        return layout

    def compute_cell_height(self, widget, width):
        treeview = self.view._treeview
        store = self.view.controller.get_store()
        if not self._row_needs_exact_height(treeview, store):
            self.source_layout = None
            self.target_layout = None
            treeview.mark_row_estimated(self.unit)
            source_height = self._estimate_text_height(widget, self.unit.source, width / 2,
                    rendering.get_source_font_description())
            target_height = self._estimate_text_height(widget, self.unit.target, width / 2,
                    rendering.get_target_font_description())
            return max(source_height, target_height) + self.ROW_PADDING

        treeview.mark_row_measured_exactly(self.unit)
        return self._compute_exact_height(widget, width)

    def _compute_exact_height(self, widget, width):
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
        if widget.get_direction() == Gtk.TextDirection.RTL:
            self.source_layout.set_alignment(Pango.Alignment.RIGHT)
            self.target_layout.set_alignment(Pango.Alignment.RIGHT)
        _layout_width, source_height = self.source_layout.get_pixel_size()
        _layout_width, target_height = self.target_layout.get_pixel_size()
        return max(source_height, target_height) + self.ROW_PADDING

    def _row_needs_exact_height(self, treeview, store):
        if not store:
            return True
        if self._is_last_row(treeview, store):
            # scroll_to_cell() can target this row directly (#1366) -
            # an estimate here would show up as a visible jump once
            # the real height replaces it right as it's scrolled to.
            return True
        # See StoreTreeView.get_cached_visible_range()'s own comment for
        # why this isn't just treeview.get_visible_range().
        visible_range = treeview.get_cached_visible_range()
        if visible_range is None:
            return False
        start_index = visible_range[0] - self.VIEWPORT_ROW_BUFFER
        end_index = visible_range[1] + self.VIEWPORT_ROW_BUFFER
        row = self._row(treeview, store)
        if row is None:
            return True
        return start_index <= row <= end_index

    def _last_row_padding(self, treeview):
        """Space below the last row, so scroll_to_cell() can centre it."""
        store = self.view.controller.get_store()
        if store and self._is_last_row(treeview, store):
            return max(treeview.get_allocation().height // 2, 0)
        return 0

    def _is_last_row(self, treeview, store):
        model = treeview.get_model()
        if isinstance(model, StoreTreeModel):
            return model.row_count() > 0 and self.unit is model.unit_at_row(model.row_count() - 1)
        return self.unit is store[-1]

    def _row(self, treeview, store):
        """This unit's row number, or C{None}."""
        index = self._unit_index(store)
        model = treeview.get_model()
        if index is None or not isinstance(model, StoreTreeModel):
            return index
        path = model.store_index_to_path(index)
        return None if path is None else path[0]

    def _unit_index(self, store):
        cache = self._index_cache
        if cache is None or cache[0] is not store or cache[1] != len(store):
            index_by_id = {id(unit): i for i, unit in enumerate(store)}
            cache = (store, len(store), index_by_id)
            self._index_cache = cache
        return cache[2].get(id(self.unit))

    def _font_metrics(self, widget, font_description):
        # get_metrics() does a real font lookup - worth caching across
        # thousands of rows that all share the same handful of fonts.
        key = font_description.to_string()
        cached = self._metrics_cache.get(key)
        if cached is None:
            context = widget.get_pango_context()
            metrics = context.get_metrics(font_description, None)
            cached = (
                max(metrics.get_approximate_char_width(), 1),
                metrics.get_ascent() + metrics.get_descent(),
            )
            self._metrics_cache[key] = cached
        return cached

    def _estimate_text_height(self, widget, text, width, font_description):
        """A cheap, unshaped height estimate (character count against
        the font's average advance width) - skips building or measuring
        an actual Pango.Layout entirely."""
        char_width, line_height = self._font_metrics(widget, font_description)
        chars_per_line = max(1, (width * Pango.SCALE) // char_width)
        lines = text.split('\n') if text else ['']
        num_lines = sum(-(-max(len(line), 1) // chars_per_line) for line in lines)
        return (line_height * max(num_lines, 1)) / Pango.SCALE

    def check_editor_height(self, editor, width, parentheight):
        notesheight = 0

        for note in editor._widgets['notes'].values():
            _minimum, natural = note.get_preferred_size()
            notesheight += natural.height

        maxheight = parentheight - notesheight

        if maxheight < 0:
            return

        visible_textboxes = []
        for textbox in (editor._widgets['sources'] + editor._widgets['targets']):
            if textbox.props.visible:
                visible_textboxes.append(textbox)

        max_tb_height = maxheight / len(visible_textboxes)

        for textbox in visible_textboxes:
            _minimum, natural = textbox.get_parent().get_preferred_size()
            if textbox.props.visible and natural.height > max_tb_height:
                textbox.get_parent().set_size_request(-1, max_tb_height)
                #logging.debug('%s.set_size_request(-1, %d)' % (textbox.parent, max_tb_height))


    # EVENT HANDLERS #
    def _on_editor_done(self, editor):
        self.emit("editing-done", editor.get_path(), editor.must_advance, editor.is_modified())
        return True

    def _on_modified(self, widget):
        self.emit("modified")
