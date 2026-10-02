#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
from bisect import bisect_left

from gi.repository import GObject

from virtaal.common import GObjectWrapper


class Cursor(GObjectWrapper):
    """
    Manages the current position in an arbitrary model.

    NOTE: Assigning to C{self.pos} causes the "cursor-changed" signal
    to be emitted.
    """

    __gtype_name__ = "Cursor"

    __gsignals__ = {
        "cursor-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "cursor-empty":   (GObject.SignalFlags.RUN_FIRST, None, ()),
        "indices-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }


    # INITIALIZERS #
    def __init__(self, model, indices, circular=True):
        """Constructor.
            @type  model: anything
            @param model: The model (usually a collection) to which the cursor is applicable.
            @type  indices: ordered collection
            @param indices: The valid values for C{self.index}."""
        GObjectWrapper.__init__(self)

        self.model = model
        self._indices = indices
        self.circular = circular

        self._pos = 0
        # The index before indices last became empty, so refilling them
        # puts the cursor back near the same unit.
        self._last_index = 0
        # A unit the cursor is on without it being in indices - see visit().
        self._visiting = None


    # ACCESSORS #
    def _get_pos(self):
        return self._pos
    def _set_pos(self, value):
        if not self._indices:
            return
        if value == self._pos:
            return # Don't unnecessarily move the cursor (or emit 'cursor-changed', more specifically)
        if value >= len(self.indices):
            self._pos = len(self.indices) - 1
        elif value < 0:
            self._pos = 0
        else:
            self._pos = value
        self.emit('cursor-changed')
    pos = property(_get_pos, _set_pos)

    def _get_index(self):
        if self._visiting is not None:
            return self._visiting
        l_indices = len(self._indices)
        if l_indices < 1:
            return -1
        if self.pos >= l_indices:
            return l_indices - 1
        return self._indices[self.pos]
    def _set_index(self, index):
        """Move the cursor to the cursor to the position specified by C{index}.
            @type  index: int
            @param index: The index that the cursor should point to."""
        was_visiting = self._visiting is not None
        self._visiting = None
        oldpos = self._pos
        self.pos = bisect_left(self._indices, index)
        if was_visiting and self._indices and self._pos == oldpos:
            self.emit('cursor-changed')
    index = property(_get_index, _set_index)

    def _get_indices(self):
        return self._indices
    def _set_indices(self, value):
        self._replace_indices(value)
        self.emit('indices-changed')
    indices = property(_get_indices, _set_indices)

    def _replace_indices(self, value):
        visiting = self._visiting
        oldindex = self.index if self._indices else self._last_index
        oldpos = self.pos

        self._indices = list(value)

        if visiting is not None:
            # Stay on the visited unit; it may now be in indices.
            if visiting in self._indices:
                self._visiting = None
                self._pos = self._indices.index(visiting)
            else:
                self._pos = min(bisect_left(self._indices, visiting), max(len(self._indices) - 1, 0))
            if not self._indices:
                self.emit('cursor-empty')
            return

        if not self._indices:
            # No 'cursor-changed': there is no unit to change to, and
            # listeners would otherwise be handed index -1.
            self._last_index = oldindex
            self._pos = 0
            self.emit('cursor-empty')
            return

        self.index = oldindex
        if oldpos == self.pos and oldindex != self.index:
            self.emit('cursor-changed')

    # METHODS #
    def deref(self):
        """Dereference the cursor to the item in the model that the cursor is
            currently pointing to.

            @returns: C{self.model[self.index]}, or C{None} if any error occurred."""
        if self._visiting is None and not self._indices:
            # index is -1 here, which would silently deref the last item.
            return None
        try:
            return self.model[self.index]
        except Exception as exc:
            logging.debug('Unable to dereference cursor:\n%s' % (exc))
            return None

    def visit(self, index):
        """Move the cursor to C{index} even if it isn't in C{self.indices},
            without adding it: the next move goes to the nearest unit in
            C{self.indices} by position."""
        if index in self._indices:
            self.index = index
            return
        if index == self._visiting:
            return
        self._visiting = index
        self.emit('cursor-changed')

    def force_index(self, index):
        """Move the cursor to C{index}, visiting it if it isn't in C{self.indices}."""
        self.visit(index)

    def move(self, offset):
        """Move the cursor C{offset} positions down.
            The cursor will wrap around to the beginning if C{circular=True}
            was given when the cursor was created."""
        if not self._indices:
            return
        if self._visiting is not None:
            # Offset 1 is the first unit in indices after the visited one.
            after = bisect_left(self._indices, self._visiting)
            target = after + offset - 1 if offset > 0 else after + offset
            if not 0 <= target < len(self._indices):
                if not self.circular:
                    raise IndexError()
                target %= len(self._indices)
            self._visiting = None
            self._pos = target
            self.emit('cursor-changed')
            return
        if self.circular:
            self.pos = (self.pos + offset) % len(self._indices)
        elif 0 <= self.pos + offset < len(self._indices):
            self.pos += offset
        else:
            raise IndexError()
