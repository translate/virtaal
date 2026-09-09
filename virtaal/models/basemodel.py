#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GObject


class BaseModel(GObject.GObject):
    """Base class for all models."""

    __gtype_name__ = "BaseModel"

    __gsignals__ = {
        "loaded": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "saved": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # INITIALIZERS #
    def __init__(self):
        super().__init__()


    # ACCESSORS #
    def is_modified(self):
        return False

    # METHODS #
    def loaded(self):
        """Emits the "loaded" signal."""
        self.emit('loaded')

    def saved(self):
        """Emits the "saved" signal."""
        self.emit('saved')
