
.. _checks#quality_checks:

Quality Checks
**************

.. versionadded:: 0.7

Virtaal provides a powerful way of reviewing translations for quality. It
exposes most of the :ref:`pofilter checks <toolkit:pofilter_tests>` that can
test for several issues that can affect the quality of your translations.

If Virtaal indicates a possible problem with a translation, it doesn’t mean
that the translation is necessarily wrong, just that you might want to review
it. You should also select the correct project type (GNOME, KDE, Mozilla, etc.)
in the project type selection. This will improve the accuracy of the quality
checks.

Virtaal shows the results of the quality checks in two ways: interactively for
the current unit while you type, and as a navigation mode, similar to searching
or "incomplete" mode.

.. _checks#interactive_checking:

Interactive checking
====================
Virtaal will perform the quality checks on the current translation while you
type. Only the names of the possible issues are listed, but you can click on
them for more detail. The same details can also be shown by pressing F8. This
might explain what the test mean, or could even mention detailed information
about the possible error.

You can also read the detailed descriptions of the
:ref:`pofilter checks <toolkit:pofilter_tests>`.

.. _checks#quality_checks_navigation_mode:

Quality checks navigation mode
==============================
In the "Quality checks" navigation mode, you can select certain quality checks
from the list of possible issues seen by Virtaal. The navigation mode allows
for batch review of quality checks. Selecting the name of a test will step you
through the translations that fail the test.

At each translation you have access to the test details as described above.

You might need to save to ensure that the navigation results are up to date.
