#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""These are some tips that are displayed to the user."""

from gettext import gettext as _


tips = [
    _("At the end of a translation, simply press <Enter> to continue with the next one."),
    _("To copy the original string into the target field, simply press <Alt+Down>."),
    #_("When editing a fuzzy translation, the fuzzy marker will automatically be removed."),
    # l10n: Refer to the translation of "Fuzzy" to find the appropriate shortcut key to recommend
    _("To mark the current translation as fuzzy, simply press <Alt+U>."),
    _("To mark the current translation as incomplete, simply press <Ctrl+Shift+Enter>."),
    _("To mark the current translation as complete, simply press <Ctrl+Enter>."),
    _("Use Ctrl+Up or Ctrl+Down to move between translations."),
    _("Use Ctrl+PgUp or Ctrl+PgDown to move in large steps between translations."),
]
