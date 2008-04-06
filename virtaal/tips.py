# These are some tips that are displayed to the user

import gettext

_ = gettext.gettext

tips = [
_("At the end of a translation, simply press <Enter> to continue with the next one."),
# l10n: Refer to the translation of "Copy to target" to find the appropriate shortcut key to recommend
_("To copy the original string into the target field, simply press <Alt+C>."),
_("When editing a fuzzy translation, the fuzzy marker will automatically be removed."),
# l10n: Refer to the translation of "Fuzzy" to find the appropriate shortcut key to recommend
_("To mark the current translation as fuzzy, simply press <Alt+U>."),
]
