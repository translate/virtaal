#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.


class BaseMode:
    """Interface for other modes."""
    name = 'BaseMode'
    """The internal name of the mode."""
    display_name = ''
    """Subclasses should mark this for translation with _()"""
    widgets = []

    # INITIALIZERS #
    def __init__(self, mode_controller):
        raise NotImplementedError()


    # METHODS #
    def selected(self):
        """Signals that this mode has just been selected by the given document."""
        raise NotImplementedError()

    def unselected(self):
        """This is run right before the mode is unselected."""
        raise NotImplementedError()
