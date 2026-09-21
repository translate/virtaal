#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import cairo
import pytest
from gi.repository import Gtk
from translate.storage.placeables import StringElem

from virtaal.views import rendering
from virtaal.views.placeablesguiinfo import NewlineGUI
from virtaal.views.widgets.storecellrenderer import (
    StoreCellRenderer,
    compute_optimal_height,
)


def test_compute_optimal_height_unregistered_type_raises():
    with pytest.raises(NotImplementedError):
        compute_optimal_height(object(), 100)


def test_compute_optimal_height_widget_is_a_noop():
    # Gtk.Widget itself is abstract - Gtk.Separator is a plain concrete
    # widget with no more specific registration of its own, so it
    # dispatches to the Gtk.Widget handler.
    widget = Gtk.Separator()
    compute_optimal_height(widget, 100)  # must not raise


def test_compute_optimal_height_label_sets_size_request():
    label = Gtk.Label(label='hello')
    compute_optimal_height(label, 200)

    assert label.get_size_request() == (200, label.get_size_request()[1])
    assert label.get_size_request()[1] > 0


def _realized_textview(text, pilcrows=0):
    """A real, off-screen-rendered Gtk.TextView with `text` as its
    content - optionally with `pilcrows` real NewlineGUI pilcrow
    widgets (the actual production class, not a stand-in - its
    deliberately-small size_request, smaller than a line of text, is
    exactly what makes this bug real), one inserted before each of
    `text`'s first `pilcrows` newlines."""
    win = Gtk.OffscreenWindow()
    textview = Gtk.TextView()
    textview.role = 'target'
    # unitview.py sets this on every real textview regardless of
    # placeables - without it, a NewlineGUI's own font override (it
    # sets the same font, but only as a side effect of existing) makes
    # a with-pilcrow textview measure in a different font than a plain
    # one, comparing two fonts' line heights instead of the
    # placeable's actual contribution.
    rendering.set_widget_font(textview, rendering.get_target_font_description())
    textview.get_pango_context().set_font_description(rendering.get_target_font_description())
    buf = textview.get_buffer()
    remaining = pilcrows
    while remaining and '\n' in text:
        before, text = text.split('\n', 1)
        buf.insert(buf.get_end_iter(), before)
        widget = NewlineGUI(StringElem('\n'), textview).widgets[0]
        anchor = buf.create_child_anchor(buf.get_end_iter())
        textview.add_child_at_anchor(widget, anchor)
        widget.show()
        buf.insert(buf.get_end_iter(), '\n')
        remaining -= 1
    buf.insert(buf.get_end_iter(), text)
    win.add(textview)
    win.show_all()
    return textview


def test_compute_optimal_height_textview_matches_a_plain_two_line_estimate():
    textview = _realized_textview('First line.\nSecond line.')
    compute_optimal_height(textview, 200)

    assert textview.get_parent().get_size_request()[1] > 0


def test_compute_optimal_height_textview_accounts_for_an_embedded_placeable_widget():
    # The plain-text Pango layout compute_optimal_height() builds its
    # estimate from has no idea about child-anchor widgets (e.g. the
    # pilcrow standing in for a newline) - those take real vertical
    # space this text-only estimate doesn't, undercounting the row
    # height needed and clipping the wrapped line below the widget
    # (#3536).
    plain = _realized_textview('First line.\nSecond line.')
    compute_optimal_height(plain, 200)
    plain_height = plain.get_parent().get_size_request()[1]

    with_pilcrow = _realized_textview('First line.\nSecond line.', pilcrows=1)
    compute_optimal_height(with_pilcrow, 200)
    pilcrow_height = with_pilcrow.get_parent().get_size_request()[1]

    assert pilcrow_height > plain_height


def test_compute_optimal_height_does_not_fully_stack_multiple_embedded_widgets():
    # A unit with several placeables needs a bit more real room than
    # one with a single one, but nowhere near each widget's full own
    # height added on top of the others - a four-pilcrow unit came out
    # roughly four times taller than it needed to be before this.
    text = 'One.\nTwo.\nThree.\nFour.'
    plain = _realized_textview(text)
    compute_optimal_height(plain, 200)
    plain_height = plain.get_parent().get_size_request()[1]

    pilcrow_holder = _realized_textview('\n', pilcrows=1)
    pilcrow_natural_height = pilcrow_holder.get_children()[0].get_preferred_height()[1]

    three_pilcrows = _realized_textview(text, pilcrows=3)
    compute_optimal_height(three_pilcrows, 200)
    three_pilcrows_height = three_pilcrows.get_parent().get_size_request()[1]

    assert plain_height < three_pilcrows_height < plain_height + 3 * pilcrow_natural_height


def test_compute_optimal_height_reflects_a_reused_widgets_new_content():
    # A unit switch reuses the same editor widget - the old anchor
    # widget is destroyed and a new one created for the new unit's
    # content, so this must look at the widget's current children each
    # time, not anything cached from an earlier call.
    textview = _realized_textview('First line.\nSecond line.')
    compute_optimal_height(textview, 200)
    plain_height = textview.get_parent().get_size_request()[1]

    buf = textview.get_buffer()
    buf.set_text('First line.')
    widget = NewlineGUI(StringElem('\n'), textview).widgets[0]
    anchor = buf.create_child_anchor(buf.get_end_iter())
    textview.add_child_at_anchor(widget, anchor)
    widget.show()
    buf.insert(buf.get_end_iter(), '\nSecond line.')
    compute_optimal_height(textview, 200)
    pilcrow_height = textview.get_parent().get_size_request()[1]

    assert pilcrow_height > plain_height


def test_compute_optimal_height_container_skips_invisible_children():
    box = Gtk.Box()
    box.set_visible(True)
    visible_label = Gtk.Label(label='visible')
    visible_label.set_visible(True)
    hidden_label = Gtk.Label(label='hidden')
    hidden_label.set_visible(False)
    box.add(visible_label)
    box.add(hidden_label)

    compute_optimal_height(box, 200)

    assert visible_label.get_size_request()[0] == 200
    assert hidden_label.get_size_request() == (-1, -1)


def _rectangle(width=10, height=10):
    return SimpleNamespace(x=0, y=0, width=width, height=height)


def _blank_pixel(fuzzy, flags):
    """Paint into a fresh transparent surface and return its first
    pixel - non-zero means something was actually painted there."""
    renderer = StoreCellRenderer(None)
    renderer.unit = SimpleNamespace(isfuzzy=lambda: fuzzy)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10)
    cr = cairo.Context(surface)

    renderer._paint_fuzzy_background_if_selected(cr, _rectangle(), flags)

    surface.flush()
    return bytes(surface.get_data()[:4])


def test_paints_fuzzy_background_when_selected():
    # GTK only honours cell_background while a row isn't selected - the
    # selection highlight otherwise unconditionally replaces it,
    # hiding the fuzzy indicator on exactly the rows a translator is
    # most likely to have selected (#3321).
    assert _blank_pixel(fuzzy=True, flags=Gtk.CellRendererState.SELECTED) != b'\x00\x00\x00\x00'


def test_does_not_paint_when_not_selected():
    # GTK's own cell_background already handles this case correctly.
    assert _blank_pixel(fuzzy=True, flags=Gtk.CellRendererState(0)) == b'\x00\x00\x00\x00'


def test_does_not_paint_a_selected_non_fuzzy_row():
    assert _blank_pixel(fuzzy=False, flags=Gtk.CellRendererState.SELECTED) == b'\x00\x00\x00\x00'
