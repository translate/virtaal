#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 Zuza Software Foundation
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

import gobject
import gtk

__all__ = ['pulse']

COL_RED, COL_GREEN, COL_BLUE = range(3)


def pulse_step(widget, steptime, colordiff, stopcolor, component):
    """Performs one step in the fade.
        @param widget: The widget being faded.
        @param steptime: The duration (ms) of this step.
        @param colordiff: Tuple of RGB-deltas to be added to the current
            colour.
        @param stopcolor: Don't queue another iteration if we've reached this,
            our target colour."""
    if len(colordiff) < 3:
        raise ValueError('colordiff does not have all colour deltas')

    col = getattr(widget.style, component)[gtk.STATE_NORMAL]
    modify_func = getattr(widget, 'modify_%s' % (component))

    # Check if col's values have not overshot stopcolor, taking into
    # account the sign of the colordiff element (colordiff[x]/abs(colordiff[x])).
    # FIXME: I'm sure the conditions below have a more mathematically elegant
    # solution, but my brain is too melted at the moment to see it.
    if (colordiff[COL_RED] == 0 or (colordiff[COL_RED] > 0 and col.red+colordiff[COL_RED] >= stopcolor[COL_RED]) or (colordiff[COL_RED] < 0 and col.red+colordiff[COL_RED] <= stopcolor[COL_RED])) and \
            (colordiff[COL_GREEN] == 0 or (colordiff[COL_GREEN] > 0 and col.green+colordiff[COL_GREEN] >= stopcolor[COL_GREEN]) or (colordiff[COL_GREEN] < 0 and col.green+colordiff[COL_GREEN] <= stopcolor[COL_GREEN])) and \
            (colordiff[COL_BLUE] == 0 or (colordiff[COL_BLUE]  > 0 and col.blue+colordiff[COL_BLUE] >= stopcolor[COL_BLUE]) or (colordiff[COL_BLUE] < 0 and col.blue+colordiff[COL_BLUE] <= stopcolor[COL_BLUE])):
        # Pulse overshot, restore stopcolor and end the fade
        col = gtk.gdk.Color(
            red=stopcolor[COL_RED],
            green=stopcolor[COL_GREEN],
            blue=stopcolor[COL_BLUE]
        )
        modify_func(gtk.STATE_NORMAL, col)
        #logging.debug(
        #    'Pulse complete (%d, %d, %d) > (%d, %d, %d)' %
        #    (col.red, col.green, col.blue, stopcolor[COL_RED], stopcolor[COL_GREEN], stopcolor[COL_BLUE])
        #)
        return

    col.red   += colordiff[COL_RED]
    col.green += colordiff[COL_GREEN]
    col.blue  += colordiff[COL_BLUE]

    if col.red == stopcolor[COL_RED] and \
            col.green == stopcolor[COL_GREEN] and \
            col.blue  == stopcolor[COL_BLUE]:
        # Pulse complete
        modify_func(gtk.STATE_NORMAL, col)
        return

    modify_func(gtk.STATE_NORMAL, col)
    gobject.timeout_add(steptime, pulse_step, widget, steptime, colordiff, stopcolor, component)

def pulse(widget, color, fadetime=5000, steptime=10, component='bg'):
    """Fade the background colour of the current widget from the given colour
        back to its original background colour.
        @type  widget: gtk.Widget
        @param widget: The widget to pulse.
        @param color: Tuple of RGB-values.
        @param fadetime: The total duration (in ms) of the fade.
        @param steptime: The number of steps that the fade should be divided
            into."""
    if not isinstance(widget, gtk.Widget):
        raise ValueError('widget is not a GTK widget')

    if not component in ('base', 'bg', 'fg'):
        raise ValueError('"component" must be either "base", "bg" or "fg"')

    modify_func = getattr(widget, 'modify_%s' % (component))

    col = getattr(widget.style, component)[gtk.STATE_NORMAL]
    nsteps = fadetime/steptime
    colordiff = (
        (col.red   - color[COL_RED])   / nsteps,
        (col.green - color[COL_GREEN]) / nsteps,
        (col.blue  - color[COL_BLUE])  / nsteps,
    )
    stopcolor = (col.red, col.green, col.blue)
    #logging.debug(
    #    'Before fade: [widget %s][steptime %d][colordiff %s][stopcolor %s]' %
    #    (widget, steptime, colordiff, stopcolor)
    #)
    pulsecol = gtk.gdk.Color(
        red=color[COL_RED],
        green=color[COL_GREEN],
        blue=color[COL_BLUE]
    )
    modify_func(gtk.STATE_NORMAL, pulsecol)
    gobject.timeout_add(steptime, pulse_step, widget, steptime, colordiff, stopcolor, component)
