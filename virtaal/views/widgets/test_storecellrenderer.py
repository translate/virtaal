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
