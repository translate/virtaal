#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010 Zuza Software Foundation
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


"""This module contains some theme dependent colors.

The colors are kept as strings so that the can easily be interpolated into
pango markup. A different solution is likely to be better in the long run."""

from gi.repository import Gtk, Gdk

INVERSE = False
"""Whether we are currently in an inverse type of theme (lite text on dark
background).

Other code wanting to alter their behaviour on whether we run in an inverse
theme or not, can inspect this to know.
"""


def rgba_to_str(c: Gdk.RGBA):
    s = ["#"]
    for f in c.to_color().to_floats():
        s.append("%x" % int(f*255))
    return "".join(s)


def str_to_rgba(s):
    rgba = Gdk.RGBA()
    rgba.parse(s)
    return rgba


_default_theme = {
    # Generic styling for a URL
    'url_fg': '#0000ff',
    'subtle_fg': 'darkgrey',
    # Colours for the selected placeable (not affected by its type)
    'selected_placeable_fg': '#000000',
    'selected_placeable_bg': '#90ee90',
    # Red warning foreground colour for things like XML markup
    'markup_warning_fg': '#8b0000', #darkred/#8b0000
    'ph_placeable_bg': '#f7f7f7',
    # warning background for things like no search result
    'warning_bg': '#f66',
    # row colour for fuzzy strings
    'fuzzy_row_bg': 'grey',
    # selector text box border
    'selector_textbox': '#5096f3',
    # diffing markup:
    # background for insertion
    'diff_insert_bg': '#a0ffa0',
    # background for deletion
    'diff_delete_bg': '#ccc',
    # background for replacement (deletion+insertion)
    'diff_replace_bg': '#ffff70',
}

_inverse_theme = {
    'url_fg': '#aaaaff',
    'subtle_fg': 'grey',
    'selected_placeable_fg': '#ffffff',
    'selected_placeable_bg': '#007010',
    'markup_warning_fg': '#ffa0a0',
    'ph_placeable_bg': '#101010',
    'warning_bg': '#900',
    'fuzzy_row_bg': '#474747',
    'selector_textbox': '#cbdffb',
    'diff_insert_bg': '#005500',
    'diff_delete_bg': '#333',
    'diff_replace_bg': '#4a4a00',
}

current_theme = _default_theme.copy()

def set_default():
    global INVERSE
    global current_theme
    INVERSE = False
    current_theme.update(_default_theme)

def set_inverse():
    global INVERSE
    global current_theme
    INVERSE = True
    current_theme.update(_inverse_theme)

def is_inverse(fg, bg):
    """Takes a guess at whether the given foreground and background colours
    represents and inverse theme (light text on a dark background)."""
    # Let's sum the three colour components to work out a rough idea of how
    # "light" the colour is:
    # TODO: consider using luminance calculation instead (probably overkill)
    bg_sum = sum((bg.red, bg.green, bg.blue))
    fg_sum = sum((fg.red, fg.green, fg.blue))
    if bg_sum < fg_sum:
        return True
    else:
        return False

def update_style(widget):
    _style = widget.get_style_context()
    _state = Gtk.StateType.NORMAL
    fg = _style.get_color(_state)
    bg = _style.get_background_color(_state)
    if is_inverse(fg, bg):
        set_inverse()
    else:
        set_default()

    fg = rgba_to_str(fg)
    bg = rgba_to_str(bg)

    # On some themes (notably Windows XP with classic style), diff_delete_bg is
    # almost identical to the background colour used. So we use something from
    # the gtk theme that is supposed to be different, but not much.
    if not has_reasonable_contrast(bg, current_theme['diff_delete_bg']):
        if INVERSE:
            new_diff_delete_bg = "#000"
        else:
            new_diff_delete_bg = "#fff"
        # we only want to change if it will actually result in something readable:
        if has_good_contrast(fg, new_diff_delete_bg):
            current_theme['diff_delete_bg'] = new_diff_delete_bg


# these are based on an (old?) Web Content Accessibility Guidelines of the w3c
# See  http://juicystudio.com/article/luminositycontrastratioalgorithm.php
# TODO: Might be a bit newer/better, so we shuld consider updating the code:
#      http://www.w3.org/TR/WCAG20/Overview.html

def _luminance(c):
    c = str_to_rgba(c)
    r = pow(c.red, 2.2)
    g = pow(c.green, 2.2)
    b = pow(c.blue, 2.2)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def _luminance_contrast_ratio(c1, c2):
    l1 = _luminance(c1)
    l2 = _luminance(c2)
    l1, l2 = max(l1, l2), min(l1, l2)
    return (l1 + 0.05) / (l2 + 0.05)

def has_good_contrast(c1, c2):
    """Takes a guess at whether the two given colours are in good contrast to
    each other (for example, to be able to be used together as foreground and
    background colour)."""
    return _luminance_contrast_ratio(c1, c2) >= 4.5

def has_reasonable_contrast(c1, c2):
    """Similarly to has_good_contrast() this says whether the two given
    colours have at least a reasonable amount of contrast, so that they would
    be distinguishable."""
    return _luminance_contrast_ratio(c1, c2) >= 1.2
    # constant determined by testing in many themes, Windows XP with "classic"
    # being the edge case
