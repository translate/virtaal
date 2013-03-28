
.. _tips#tips_and_tricks:

Tips and Tricks
***************
This page mentions some tips and tricks to get the most out of Virtaal. Some
hidden features mentioned here might just make you a little more productive, or
help you to customise things to be exactly the way you want.

Some of these features mention how to make changes to a configuration file for
Virtaal. Depending on the version of Virtaal, you might be able to do the same
inside Virtaal in the Preferences dialog. You can use any text editor to make
these changes. These files are stored in the following directory on your
system:

- Unix / Linux:  ``~/.virtaal/``
- Mac OS X: ``~/Library/Application Support/Virtaal/`` or ``~/.virtaal/``
- Windows:  ``%APPDATA%\Virtaal`` for example:

  - ``C:\Documents and Settings\%USERNAME%\Application Data\Virtaal``
  - ``C:\Users\%USERNAME%\AppData\Roaming\Virtaal``

Most features are available via easy :doc:`shortcuts <cheatsheet>`.

.. _tips#migrating_to_another_account/computer:

Migrating to Another Account/Computer
=====================================
Close Virtaal. Then find the directory with all your settings and the file
tm.db (your translation memory database). Copy the contents of the whole
directory to the corresponding directory on the other account/computer.

.. _tips#disabling_some_functionality:

Disabling some Functionality
============================
To disable some functionality like autocorrect, go to the Preferences and
deselect it from the list of plugins.

Alternatively, you can edit virtaal.ini. Under the heading "[plugin_state]",
add a line:

.. code-block:: python

  autocorrect = disabled

.. _tips#updating_the_information_stored_in_the_po_header:

Updating the Information Stored in the PO Header
================================================
You can modify the information put into the PO headers using Virtaal's
Preferences window.

For older versions, edit virtaal.ini and look for the settings "name", "email"
and "team". The field for the team can contain a description of your team and a
URL or a mailing list address -- anything really.

.. _tips#specify_a_language_for_virtaals_interface:

Specify a Language for Virtaal's Interface
==========================================
The best way to change the language of the Virtaal interface, is to change the
locale of your system. For Windows, this is done in the Control Center under
the Regional Settings, for example.

.. versionchanged:: 0.7

You can specify a language for the interface that is different from the
language of the system. To do this, first ensure that Virtaal is closed
entirely. Then open the file virtaal.ini and edit the setting "uilang" close to
the top of the file under [language] heading. Note that native window dialogs
only work when this is not set, or set to the system's language.

.. _tips#using_your_own_font_settings:

Using Your Own Font Settings
============================
You can specify your own font settings to use in the translation area. These
can be edited inside Virtaal in the Preferences.

For older versions, edit virtaal.ini, and look for the settings "sourcefont"
and "targetfont". You can therefore set the font and font size separately for
the source and target language if you wish to do so. Valid settings could look
something like this:

.. code-block:: python

   targetfont = monospace 11
   targetfont = georgia 12
   targetfont = dejavu serif,italic 9

.. _tips#receive_more_suggestions:

Receive More Suggestions
========================
If you want to receive suggestions more often, even if they are not very
similar to what you are translating, edit plugins.ini and lower the setting for
"min_quality".

If you want to receive more suggestions at a time, edit plugins.ini and
increase the setting for "max_matches".

Note that you can specify these same parameters for most of the individual
sources of TM suggestions. Try adding or editing these settings in tm.ini under
a heading corresponding to the name of the plugin.

.. _tips#make_open-tran.eu_faster:

Make Open-Tran.eu faster
========================
Do you wish the suggestions from Open-Tran.eu could come faster? The speed of
this translation memory plugin depends a lot on your network connection.  One
way that could help to make it faster, is to avoid DNS lookups. You can do that
by adding open-tran.eu into your :wp:`hosts file <Hosts_file>`.  ::

    85.214.16.47            open-tran.eu

(or whatever the IP address of open-tran.eu is)

If you don't know about hosts files and their syntax, it might be best not to
play with this setting.

