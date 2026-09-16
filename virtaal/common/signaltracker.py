#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.


class SignalTracker:
    """Tracks GObject signal connections so they can all be disconnected
    together, replacing the hand-rolled "list of (obj, signal-id) pairs,
    bulk-disconnect in destroy()" idiom several model/view classes
    otherwise reimplement themselves."""

    def __init__(self):
        self._ids = []

    def connect(self, obj, signal_name, handler, *args):
        signal_id = obj.connect(signal_name, handler, *args)
        self._ids.append((obj, signal_id))
        return signal_id

    def disconnect_all(self):
        for obj, signal_id in self._ids:
            obj.disconnect(signal_id)
        self._ids = []
