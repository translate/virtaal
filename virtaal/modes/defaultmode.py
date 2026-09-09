#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from .basemode import BaseMode


class DefaultMode(BaseMode):
    """Default mode - Include all units."""

    name = 'Default'
    display_name = _("All")
    widgets = []

    # INITIALIZERS #
    def __init__(self, controller):
        """Constructor.
            @type  controller: virtaal.controllers.ModeController
            @param controller: The ModeController that managing program modes."""
        self.controller = controller


    # METHODS #
    def selected(self):
        cursor = self.controller.main_controller.store_controller.cursor
        if not cursor or not cursor.model:
            return
        cursor.indices = cursor.model.stats['total']

    def unselected(self):
        pass
