.. _cli_options#cli_options:

Command Line Options
*********************

.. program:: virtaal

Besides opening a file by clicking on it, Virtaal can be launched directly
from the command line::

  virtaal [options] [filename]

``filename`` is optional, and is the translation file to open on startup (see
:ref:`Opening a File <using_virtaal#opening_a_file>`).

.. option:: -h, --help

   Show a summary of these options and exit.

.. option:: -v, --version

   Print Virtaal's version and exit.

.. option:: -l <filename>, --log <filename>

   Turn on logging, storing the result to the supplied filename. Use ``-``
   or ``STDOUT`` to log to the console instead of a file.

.. option:: -c <filename>, --config <filename>

   Use the configuration file given by the supplied filename, instead of
   Virtaal's default configuration location.

.. option:: -D, --debug

   Enable debugging features, and turn on debug-level logging (see
   :option:`--log`).

.. option:: --pseudo-translation

   Wrap every translatable UI string in brackets (e.g. ``[Save]``), using a
   synthetic pseudo-translation rather than a real one. Useful for spotting
   hardcoded strings and layout truncation. Mutually exclusive with
   :option:`--pseudo-translation-bidi` and :option:`--lang`.

.. option:: --pseudo-translation-bidi

   Like :option:`--pseudo-translation`, but also wraps every string in
   Unicode right-to-left isolate marks, simulating a right-to-left UI layout
   while keeping the text itself readable. Mutually exclusive with
   :option:`--pseudo-translation` and :option:`--lang`.

.. option:: --lang <language>

   Override the UI language for this run, without changing the saved
   Preferences setting. Mutually exclusive with :option:`--pseudo-translation`
   and :option:`--pseudo-translation-bidi`. ``<language>`` is one of:

   - a language code (e.g. ``fr``) - Virtaal must have a translation for it
     (see :doc:`localising_virtaal`).
   - ``en`` - Virtaal's own untranslated source strings.
   - ``system`` - the OS's own default locale, ignoring the saved
     Preferences setting.

.. option:: -P <filename>, --profile <filename>

   Perform profiling, storing the result to the supplied filename in
   KCacheGrind format. Only available in a development checkout, not in a
   packaged build.
