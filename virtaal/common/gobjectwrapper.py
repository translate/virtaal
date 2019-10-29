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

from gi.repository import GObject
#import logging


class GObjectWrapper(GObject.GObject):
    """
    A wrapper for GObject sub-classes that provides some more powerful signal-
    handling.
    """

    # INITIALIZERS #
    def __init__(self):
        super(GObjectWrapper, self).__init__()
        self._all_signals = GObject.signal_list_names(self)
        self._enabled_signals = set(self._all_signals)


    # METHODS #
    def disable_signals(self, signals=None):
        """Disable all or specified signals."""
        if signals:
            for sig in signals:
                self._enabled_signals.discard(sig)
        else:
            self._enabled_signals.clear()

    def enable_signals(self, signals=None):
        """Enable all or specified signals."""
        if signals:
            for sig in signals:
                self._enabled_signals.add(sig)
        else:
            self._enabled_signals = set(self._all_signals)  # Enable all signals

    def emit(self, signame, *args):
        if signame in self._enabled_signals:
            #logging.debug('emit("%s", %s)' % (signame, ','.join([repr(arg) for arg in args])))
            super(GObjectWrapper, self).emit(signame, *args)
