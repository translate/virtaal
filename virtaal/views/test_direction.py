#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gtk

from virtaal.views.direction import fix_expander_direction


@pytest.fixture
def default_direction():
    """Sets the default direction for widgets made in the test."""
    old = Gtk.Widget.get_default_direction()
    yield Gtk.Widget.set_default_direction
    Gtk.Widget.set_default_direction(old)


def _label_x(expander):
    window = Gtk.OffscreenWindow()
    window.set_size_request(300, -1)
    window.add(expander)
    window.show_all()
    x, _y = expander.get_label_widget().translate_coordinates(expander, 0, 0)
    width = expander.get_label_widget().get_allocated_width()
    window.destroy()
    return x, width


def test_an_expander_made_right_to_left_keeps_its_title_at_the_left(default_direction):
    # The GTK bug fix_expander_direction() works around.
    default_direction(Gtk.TextDirection.RTL)

    x, _width = _label_x(Gtk.Expander(label='Features'))

    assert x == 0


def test_fix_expander_direction_puts_the_title_at_the_right(default_direction):
    default_direction(Gtk.TextDirection.RTL)
    expander = Gtk.Expander(label='Features')

    fix_expander_direction(expander)
    x, width = _label_x(expander)

    assert x + width > 250  # beside the arrow at the right edge
    assert expander.get_direction() == Gtk.TextDirection.RTL


def test_fix_expander_direction_leaves_left_to_right_alone(default_direction):
    default_direction(Gtk.TextDirection.LTR)
    expander = Gtk.Expander(label='Features')

    fix_expander_direction(expander)
    x, _width = _label_x(expander)

    assert x < 30  # just after the arrow
    assert expander.get_direction() == Gtk.TextDirection.LTR
