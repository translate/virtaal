#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gtk

from virtaal.views.widgets.storecellrenderer import compute_optimal_height


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
