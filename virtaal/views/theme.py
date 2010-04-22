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

import gtk

INVERSE = False
"""Whether we are currently in an inverse type of theme (lite text on dark
background).

Other code wanting to alter their behaviour on whether we run in an inverse
theme or not, can inspect this to know.
"""

_default_theme = {
    # Generic styling for a URL
    'url_fg': '#0000ff',
    'subtle_fg': 'darkgrey',
    # Colours for the selected placeable (not affected by its type)
    'selected_placeable_fg': '#000000',
    'selected_placeable_bg': '#90ee90',
    # Red warning foreground colour for things like XML markup
    'markup_warning_fg': 'darkred',
    'ph_placeable_bg': '#f7f7f7',
    # warning background for things like no search result
    'warning_bg': '#f66',
    # row colour for fuzzy strings
    'fuzzy_row_bg': 'grey',
}
# TODO:
# diffing markup - check virtaal/views/markup.py

_inverse_theme = {
    'url_fg': '#aaaaff',
    'subtle_fg': 'grey',
    'selected_placeable_fg': '#ffffff',
    'selected_placeable_bg': '#007010',
    'markup_warning_fg': '#ff3030',
    'ph_placeable_bg': '#101010',
    'warning_bg': '#900',
    'fuzzy_row_bg': '#555555',
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
    # Let's some the three colour components to work out a rough idea of how
    # "light" the colour is:
    bg_sum = sum((bg.red, bg.green, bg.blue))
    fg_sum = sum((fg.red, fg.green, fg.blue))
    if bg_sum < fg_sum:
        return True
    else:
        return False

def update_style(widget):
    fg = widget.style.fg[gtk.STATE_NORMAL]
    bg = widget.style.base[gtk.STATE_NORMAL]
    if is_inverse(fg, bg):
        set_inverse()
    else:
        set_default()
