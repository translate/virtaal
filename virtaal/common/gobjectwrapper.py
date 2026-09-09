#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GObject

#import logging


class GObjectWrapper(GObject.GObject):
    """
    A wrapper for GObject sub-classes that provides some more powerful signal-
    handling.
    """

    # INITIALIZERS #
    def __init__(self):
        super().__init__()
        self._all_signals = []
        for type_ in self.__class__.mro():
            if issubclass(type_, GObject.GObject):
                self._all_signals.extend(GObject.signal_list_names(type_))
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
            super().emit(signame, *args)
