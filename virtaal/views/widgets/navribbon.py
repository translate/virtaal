#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""A vertical strip beside the unit list showing, for the whole open
file, which units are untranslated, fuzzy, failing a check, or in a
post-translation workflow state - a Meld-style diff-overview map."""

import cairo
from gi.repository import Gdk, Gtk

from translate.storage.workflow import StateEnum

from virtaal.views.theme import current_theme, str_to_rgba


WIDTH = 10
# Below this, per-unit marks would be too thin to read reliably, so
# adjacent units get binned into one mark instead (see _on_draw()).
MIN_MARK_HEIGHT = 2

# A unit failing a quality check isn't itself a workflow state (a unit
# can be translated *and* fail a check), so it gets its own pseudo-key
# in the same severity/colour tables as the real StateEnum values.
CHECK_FAILURE = 'check_failure'

# "Most severe wins" - used both to pick a single unit's colour when
# more than one condition applies, and to pick a bin's colour when
# several units are compressed into one mark for large files. Lower
# number = more severe = wins.
_SEVERITY = {
    CHECK_FAILURE: 0,
    StateEnum.REJECTED: 1,
    StateEnum.NEEDS_WORK: 2,     # fuzzy
    StateEnum.EMPTY: 3,          # untranslated
    StateEnum.NEEDS_REVIEW: 4,
    StateEnum.UNREVIEWED: 5,     # translated, no further workflow state
    StateEnum.FINAL: 6,
}

_THEME_KEYS = {
    CHECK_FAILURE: 'ribbon_check_failure_bg',
    StateEnum.REJECTED: 'ribbon_rejected_bg',
    StateEnum.NEEDS_WORK: 'ribbon_fuzzy_bg',
    StateEnum.EMPTY: 'ribbon_untranslated_bg',
    StateEnum.NEEDS_REVIEW: 'ribbon_needs_review_bg',
    StateEnum.UNREVIEWED: 'ribbon_unreviewed_bg',
    StateEnum.FINAL: 'ribbon_final_bg',
}


class NavRibbon(Gtk.DrawingArea):
    """One coloured mark per unit (or per bin, for large files), plus
    a viewport indicator, click/drag to jump."""

    def __init__(self, main_controller, scrolled_window):
        super().__init__()
        self.main_controller = main_controller
        self.scrolled_window = scrolled_window
        # Ordered (file_id, unit_index, state_key) rather than a bare
        # (unit_index, state_key) - file_id is always 0 today, kept so
        # future multi-file support only needs to populate it, not
        # change this widget's rendering logic.
        self._marks = []
        self._bound_store_controller = None
        self._store_handler_ids = []
        self._dragging = False
        # Cached rendering of the marks themselves (everything but the
        # viewport box), keyed by allocation size - so a scroll, which
        # only moves the viewport box, doesn't repaint every mark on a
        # large file. Invalidated on the rare occasions marks actually
        # change (_on_store_changed) rather than every 'draw'.
        self._marks_surface = None
        self._marks_surface_size = None

        self.set_size_request(WIDTH, -1)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )

        self.connect('draw', self._on_draw)
        self.connect('button-press-event', self._on_button_press)
        self.connect('button-release-event', self._on_button_release)
        self.connect('motion-notify-event', self._on_motion_notify)

        vadjustment = self.scrolled_window.get_vadjustment()
        vadjustment.connect('value-changed', self._on_viewport_changed)
        vadjustment.connect('changed', self._on_viewport_changed)

        main_controller.connect('controller-registered', self._on_controller_registered)
        if main_controller.store_controller:
            self._bind_store_controller(main_controller.store_controller)

    # SETUP #

    def _on_controller_registered(self, main_controller, new_controller):
        if new_controller is not main_controller.store_controller:
            return
        self._bind_store_controller(new_controller)

    def _bind_store_controller(self, store_controller):
        if self._bound_store_controller is not None:
            for handler_id in self._store_handler_ids:
                self._bound_store_controller.disconnect(handler_id)
        # Matches StoreModel's own stats-refresh cadence: load and save
        # only, nothing recomputes file-wide stats per edit.
        self._bound_store_controller = store_controller
        self._store_handler_ids = [
            store_controller.connect('store-loaded', self._on_store_changed),
            store_controller.connect('store-saved', self._on_store_changed),
            store_controller.connect('store-closed', self._on_store_changed),
        ]
        self._on_store_changed(store_controller)

    def _on_store_changed(self, _store_controller):
        self._refresh_marks()
        self._marks_surface = None
        self.queue_draw()

    def _on_viewport_changed(self, _adjustment):
        self.queue_draw()

    # DATA #

    def _refresh_marks(self):
        self._marks = []
        try:
            stats = self.main_controller.store_controller.get_store_stats()
        except (AttributeError, ValueError):
            # AttributeError: 'controller-registered' fires from inside
            # StoreController.__init__(), synchronously, before that
            # constructor reaches its own "self.store = None" - a brand
            # new controller has no store yet either way.
            return
        try:
            checks = self.main_controller.store_controller.get_store_checks()
        except (AttributeError, ValueError):
            # store.checks isn't computed until QualityCheckMode first
            # runs (mode selection or a save) - stats alone are still
            # worth showing meanwhile, just without check failures yet.
            checks = {}

        failing = set()
        for indices in checks.values():
            failing.update(indices)

        state_of = {}
        for state, indices in stats.get('extended', {}).items():
            for index in indices:
                state_of[index] = state

        for index in stats['total']:
            if index in failing:
                key = CHECK_FAILURE
            else:
                key = state_of.get(index, StateEnum.UNREVIEWED)
            self._marks.append((0, index, key))  # file_id: always 0 today

    # DRAWING #

    def _on_draw(self, widget, cr):
        allocation = widget.get_allocation()
        width, height = allocation.width, allocation.height
        if len(self._marks) == 0 or height <= 0:
            return False

        if self._marks_surface is None or self._marks_surface_size != (width, height):
            self._marks_surface = self._render_marks_surface(width, height)
            self._marks_surface_size = (width, height)
        cr.set_source_surface(self._marks_surface, 0, 0)
        cr.paint()

        self._paint_viewport(cr, width, height)
        return False

    def _render_marks_surface(self, width, height):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        cr = cairo.Context(surface)
        total = len(self._marks)

        if height >= total * MIN_MARK_HEIGHT:
            mark_height = height / total
            prev_file_id = self._marks[0][0]
            for i, (file_id, _unit_index, state_key) in enumerate(self._marks):
                y = i * mark_height
                self._paint_mark(cr, width, y, mark_height, state_key)
                if file_id != prev_file_id:
                    self._paint_divider(cr, width, y)
                prev_file_id = file_id
        else:
            bin_count = max(1, int(height // MIN_MARK_HEIGHT))
            bin_height = height / bin_count
            for b in range(bin_count):
                start = int(b * total / bin_count)
                end = max(start + 1, int((b + 1) * total / bin_count))
                bin_marks = self._marks[start:end]
                state_key = min(
                    (mark[2] for mark in bin_marks), key=lambda key: _SEVERITY[key])
                self._paint_mark(cr, width, b * bin_height, bin_height, state_key)

        return surface

    def _paint_mark(self, cr, width, y, mark_height, state_key):
        rgba = str_to_rgba(current_theme[_THEME_KEYS[state_key]])
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)
        cr.rectangle(0, y, width, max(mark_height, 1))
        cr.fill()

    def _paint_divider(self, cr, width, y):
        rgba = str_to_rgba(current_theme['subtle_fg'])
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)
        cr.set_line_width(1)
        cr.move_to(0, y)
        cr.line_to(width, y)
        cr.stroke()

    def _paint_viewport(self, cr, width, height):
        adjustment = self.scrolled_window.get_vadjustment()
        span = adjustment.get_upper() - adjustment.get_lower()
        if span <= 0:
            return
        top_frac = (adjustment.get_value() - adjustment.get_lower()) / span
        height_frac = min(adjustment.get_page_size() / span, 1.0)
        box_y = top_frac * height
        box_height = max(height_frac * height, 2)

        rgba = str_to_rgba(current_theme['ribbon_viewport_bg'])
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)
        cr.rectangle(0, box_y, width, box_height)
        cr.fill()

    # INTERACTION #

    def _unit_index_at_y(self, y):
        total = len(self._marks)
        height = self.get_allocation().height
        if total == 0 or height <= 0:
            return None
        frac = min(max(y / height, 0.0), 1.0)
        position = min(int(frac * total), total - 1)
        return self._marks[position][1]

    def _jump_to_y(self, y):
        unit_index = self._unit_index_at_y(y)
        if unit_index is None:
            return
        store_controller = self.main_controller.store_controller
        if store_controller is None or store_controller.cursor is None:
            return
        # force_index(), not select_unit()/cursor.index: the ribbon
        # always reflects the whole file, so a click must jump to the
        # exact unit even if a mode (e.g. WorkflowMode) has narrowed
        # cursor.indices to a filtered subset.
        store_controller.cursor.force_index(unit_index)

    def _on_button_press(self, _widget, event):
        if event.button != 1:
            return False
        self._dragging = True
        self._jump_to_y(event.y)
        return True

    def _on_button_release(self, _widget, event):
        if event.button == 1:
            self._dragging = False
        return False

    def _on_motion_notify(self, _widget, event):
        if self._dragging:
            self._jump_to_y(event.y)
        return False
