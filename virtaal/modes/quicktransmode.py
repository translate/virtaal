#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.support.set_enumerator import UnionSetEnumerator
from virtaal.support.sorted_set import SortedSet
from .basemode import BaseMode


class QuickTranslateMode(BaseMode):
    """Quick translate mode - Include only untranslated and fuzzy units."""

    name = 'QuickTranslate'
    display_name = _("Incomplete")
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

        indices = list(UnionSetEnumerator(
            SortedSet(cursor.model.stats['untranslated']),
            SortedSet(cursor.model.stats['fuzzy'])
        ).set)

        if not indices:
            self.controller.select_default_mode()
            return

        cursor.indices = indices

    def unselected(self):
        pass
