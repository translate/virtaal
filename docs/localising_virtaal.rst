
.. _localising_virtaal#localising_virtaal:

Localising Virtaal
******************
The Virtaal project not only tries to help people with doing localisation work,
we also believe that Virtaal itself should be well localised. With this
localisation, you should not only refer to the user interface localisation, but
a complete adaptation of the functional aspects of Virtaal for your language as
well.

Very few of these customisations are required to use Virtaal, but better
customisation for your language should help users with a better user
experience, better productivity and higher quality translations.

.. _localising_virtaal#enabling_your_language:

Enabling your Language
======================

.. _localising_virtaal#display:

Display
-------
Since Virtaal uses Unicode, all languages in Unicode with an appropriate font
should display correctly. If it doesn't display correctly by default on your
system, let us know what font settings were required in Virtaal to fix it, and
some details about your platform and fonts. On GNOME Virtaal will try to use
font settings from the GNOME configuration.

.. _localising_virtaal#input:

Input
-----
Your platform input method should work correctly in Virtaal. If necessary,
select the required input method from the context menu (right click). One
`known issue <https://bugzilla.gnome.org/show_bug.cgi?id=569581>`_ affects the
US (International) keyboard layout on Windows.

.. _localising_virtaal#plural_information:

Plural Information
------------------
It is important (although not strictly required) to know the plural information
for your language so that it is easily selectable as a source or target
language. For more information, see the :wiki:`plurals page
<l10n/pluralforms>`.

.. _localising_virtaal#word_level_features:

Word Level Features
===================

.. _localising_virtaal#spell_checking:

Spell Checking
--------------
On Linux, Virtaal uses the system spell checkers as provided by Enchant for
doing :doc:`spell checking <spell_checking>`.

.. versionchanged:: 0.7

For Windows, Virtaal will download a spell checker for active languages. If
this is not working for your language, let us know about available spell
checkers and their quality and license for the developers to consider providing
to Virtaal users. 

.. _localising_virtaal#autocorrect:

Autocorrect
-----------
Virtaal uses the autocorrect files From OpenOffice.org, with a few extra ones
contributed by the community. If you don't yet have such a file set, we can
easily help you to create it. An easy start is a spreadsheet with a list of
common errors and their respective corrections.

If you are interested in a more powerful solution, feel free to provide some
code.

.. _localising_virtaal#autocomplete:

Autocomplete
------------
Automatic completion currently uses a very simple approach of remembering words
as typed. Only basic word segmentation is used. Feel free to contribute
something more advanced as needed for your language.

.. _localising_virtaal#search:

Search
------
Searching is done using the code from :ref:`pogrep <toolkit:pogrep>`. It
supports case (in)sensitive searches, regular expressions, and Unicode
normalisation. Some languages might benefit from language specific
normalisation.

.. _localising_virtaal#quality_checks:

Quality Checks
==============

.. versionadded:: 0.7

Virtaal provides access to the quality checks of :ref:`pofilter
<toolkit:pofilter>`. Several customisations are possible for your language,
like disabling some tests, customising the behaviour, or language specific
checks.

.. _localising_virtaal#more:

More
====
If you are interested in any other useful functionality that can enhance
Virtaal for use with your language, let us look at how to integrate it. Adding
extra terminology sources, translation memory services, machine translation
services is usually very simple.

Check if your language is already supported with :doc:`automatic terminology
assistance <autoterm>` and talk to the Virtaal developers about adding support
for your language.

.. _localising_virtaal#user_interface_localisation:

User Interface Localisation
===========================

Here we give some pointers to help localisers of the Virtaal interface.

Some instructions:

- Check if someone is already working on your language on `Pootle
  <http://pootle.locamotion.org/projects/virtaal/>`_
- If not, get the `Latest POT file
  <https://github.com/translate/virtaal/raw/master/po/virtaal.pot>`_
- Be very familiar with all the :doc:`features <features>` of Virtaal,
  especially :doc:`placeables <placeables>`.
- Generate the .mo file with "msgfmt -cv", and put it in your system location
  for .mo files.  You could also use the "testlocalisations" script in the po/
  directory if Virtaal if you prefer. Then run Virtaal in in your language for
  testing. Here are some issues you might want to give specific attention to:

  - Check for clashes of access keys that should be accessible in the main
    application window.  These are all the main menu items, all the items in
    the search navigation, and all the access keys in the editing area.
  - Check for the strings that have limited space to show. These should be
    marked in the PO file for your attention.  They are usually the
    descriptions of the TM backends.  Try to get suggestions from these to see
    how much space is available.  It is usually around 11 characters in the
    worst case.

- Send your translated file to one of the developers, or attach it to a bug
  report, or upload it to Pootle.
- We currently use the InnoSetup installer for building our Windows installers.
  You might want to check that the localisation for your language is there and
  an official translation.
- For translators with non-Latin scripts, you can customise the image on the
  welcome screen. Send us the text and your desired font to start the process.
  If you prefer to edit it yourself, get in contact with us and ensure you are
  working on the SVG, not the PNG.
