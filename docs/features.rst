
.. _features#virtaal_features:

Virtaal Features
****************
Virtaal has many features for beginners and advanced users.

.. _features#ideal_for_beginners:

Ideal for Beginners
===================
.. toctree::
   :maxdepth: 1
   :hidden:

   checks
   weblookups

Virtaal is perfect for the new member on your team:

- Simple and intuitive layout
- Colour highlighting
- :doc:`Quality checks <checks>`
- Displays comments from programmers and previous translators
- Displays context (like msgctxt in PO)
- Easy way to :doc:`look-up <weblookups>` selected text on the web
- Tutorial and :doc:`guide <guide/start>` for localisation available from the
  Help menu

.. _features#productive_environment:

Productive Environment
======================
Virtaal will make you more productive

.. toctree::
   :maxdepth: 1
   :hidden:

   placeables
   autoterm
   amagama

- Fast and easy navigation within the file
- Auto-correction of common mistakes
- Auto-completion of long words
- Automatic sensing of the initial cursor position
- Copying original string to target string taking your language's punctuation
  rules into account
- Highlighting and copying :doc:`placeables <placeables>` from the source text
- Easily find your work by moving between the units that are untranslated or
  fuzzy
- Automatically update the PO header when saving
- Terminology help. Suggestions can come from:

  - Local files on your computer
  - `Open-Tran.eu <http://open-tran.eu>`_
  - :doc:`Automatically downloaded terminology files <autoterm>`

- Reuse existing translations. Suggestions can come from:

  - The current file
  - Alternative translations (previous msgid in PO, or alt-trans in XLIFF)
  - Previously saved translations
  - `Open-Tran.eu <http://open-tran.eu>`_
  - A team / office TM server
  - A tinyTM server
  - :doc:`Amagama <amagama>`

- Machine translation

  - :doc:`Google Translate <google>`
  - :doc:`Microsoft Translator <microsofttranslator>`
  - :doc:`apertium`
  - :doc:`moses`

.. toctree::
   :maxdepth: 1
   :hidden:

   google
   microsofttranslator
   apertium
   moses


.. _features#wide_format_support:

Wide Format Support
===================
Virtaal supports many file formats:

- Gettext (.po and .mo)
- XLIFF (.xlf)
- TMX
- TBX
- WordFast TM (.txt)
- Qt Linguist (.ts)
- Qt Phrase Book (.qph)
- OmegaT glossary (.tab and .utf8)

.. _features#more:

More
====
.. toctree::
   :maxdepth: 1
   :hidden:

   spell_checking

- Search and replace with regular expressions and Unicode normalisation
- :doc:`spell_checking` for translation and original text
- Word and string based translation statistics in file properties
- Uses language codes from :wp:`ISO 639-1` if available, or otherwise from
  :wp:`ISO 639-3`. Arbitrary IETF language tags as described in :wp:`BCP 47`
  can be used.
- Export .po files to .mo
- Support for inverse colour schemes for accessibility.
- Designed to also work well on small screens.
- Debug compiled application translations by opening .mo and .qm files directly
- Platform independence means you can run Virtaal on Windows, Linux, Mac OSX
  and probably other systems as well.
- Native window dialogs on Gnome, KDE, Windows and OSX
