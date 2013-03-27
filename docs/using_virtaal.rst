
.. _using_virtaal#using_virtaal:

Using Virtaal
*************
Virtaal is meant to be powerful yet simple to use. You can increase your
productivity by ensuring you know all the shortcuts and tricks and without
being distracted by a cluttered interface. 

Although most features are available using the mouse, Virtaal is designed to
encourage you to work as much as possible with your keyboard to increase your
speed and keep the translation fun.

When you have no file open in Virtaal, you'll see the Virtaal dashboard with
helpful links to your recent files and various common tasks in the program.

.. _using_virtaal#opening_a_file:

Opening a file
==============
Mostly you should be able to simply open a translation file by clicking on the
file in your file manager (Windows Explorer, Nautilus, Konqueror, etc.). The
file might be associated with another program in which case you can look for
Virtaal in the context menu by right-clicking on the file.

You can also run Virtaal and open a file with File->Open or Ctrl+O.

You can invoke Virtaal from the command line with ::

    virtaal <filename>

A list of supported translation formats can be found on the :doc:`features
<features>` page.

.. _using_virtaal#normal_translation:

Normal translation
==================
After opening a file, the first translation unit will be shown, with your
cursor in the field below the source text. You can simply type your translation
and press <Enter> when finished - just like in your word processor.

Note that <Enter> moves you to the next position where you want to type. In the
case of units with :doc:`plurals <guide/translation/plurals>`, enter will take
you to the next line in the same unit.

If you have the correct :doc:`spell checkers <spell_checking>` installed, spell
checking should be active for both the source and the target text.

You can undo normally using Ctrl+Z.

.. _using_virtaal#time_savers:

Time savers
===========

.. _using_virtaal#auto-completion:

Auto-completion
---------------
Virtaal will save you some time by trying to complete some long words for you.
Users of OpenOffice.org will already love this feature. You will see the
auto-completion suggesting a possible word, and the suggestion can be accepted
by pressing <Tab>. If the suggestion is not what you want, you can simply
continue typing the word you had in mind. If you accepted a suggestion that you
don't want, you can simply undo normally with Ctrl+Z.

.. _using_virtaal#auto-correction:

Auto-correction
---------------
Virtaal will save you some time by fixing certain common typing mistakes or
spelling errors. Users of OpenOffice.org will already love this feature. How
mistakes are corrected depends on your language, and there might possibly not
be information for your language yet. Feel free to get involved in the project
to improve this feature for your language.

If Virtaal automatically corrected something which you didn't want, you can
simply undo the step with Ctrl+Z.

.. _using_virtaal#copy_original_to_target:

Copy original to target
-----------------------
Sometimes it is easier to have the original string as a start to only replace a
few translatable elements. Translations containing XML markup or many variables
might be more work to type again than to just start with the source text. You
can easily copy the original text into your translation area by pressing
<Alt+Down>.

For some languages, you will see how Virtaal automatically changes the
punctuation marks to fit the conventions of your language. This could involve
quotation or other punctuation marks, or the spacing between certain elements.
For example, a "quotation" automatically becomes a « quotation » in French,
without the translator having to change the quote characters or the spacing.

If you don't want the changes to the source text that Virtaal automatically
did, you can simply undo the step with Ctrl+Z.

.. _using_virtaal#copy_a_placeable_to_the_target:

Copy a placeable to the target
------------------------------

:doc:`Placeables <placeables>` are special parts of the text that can be
automatically highlighted and easily inserted into the translation. You will
see that certain parts of the source text will be highlighted. To select which
placeable to insert, press <Alt+Right> to move the highlighting to the correct
placeable.  You can insert the currently highlighted placeable by pressing
<Alt+Down>.  After you have inserted a placeable, the next placeable will be
highlighted.

.. _using_virtaal#copy_a_term_to_the_target:

Copy a term to the target
-------------------------

Highlighted text will show which terms Virtaal recognised, and allow you to
handle them as placeables. You can use <Alt+Right> and <Alt+Down> the same way
as with other placeables. If there is more than one suggestion for a term,
Virtaal will display the choices in a menu. Select the translation you want, or
press <Escape> to continue typing.

.. _using_virtaal#use_a_suggestion_from_tm_or_mt:

Use a suggestion from TM or MT
------------------------------
If Virtaal has a suggestion obtained from translation memory or machine
translation, it is displayed underneath the editing area. You can put the first
suggestion into the target text with Ctrl+1, or use Ctrl+2, etc. to select the
others. You can also double click the suggestion to obtain the same effect.

.. _using_virtaal#navigation:

Navigation
==========
Above we saw how we can easily advance to the next point of translation by
pressing <Enter>. You can also move around easily between rows with <Ctrl+Down>
and <Ctrl+Up>. To move in large steps, use <Ctrl+PgDown> and <Ctrl+PgUp>.

.. _using_virtaal#incomplete_mode:

Incomplete mode
---------------
Virtaal will move you between certain rows. Normally it will move between all
rows, but if you activate the "Incomplete" mode, it will move between
untranslated and fuzzy units. This allows you to quickly find the places where
you need to work. Translations will still appear between the same rows in the
file so that you can see the context that you are translating in.

.. _using_virtaal#workflow_mode:

Workflow mode
-------------
This mode allows you to move between specific units sharing the same state(s),
which can be specified in detail. For example, with a PO file you could move
across translated items, or only untranslated ones. Or with XLIFF, you could
move only across units that need more work, review process, or both.

.. _using_virtaal#searching_mode:

Searching mode
--------------
Activate searching mode in the mode selector at the top, or simply press <F3>.
Virtaal will then move between all the rows that correspond to your search
query. Translations will still appear between the same rows in the file so that
you can see the context that you are translating in.

To move back from the search box to your translation, simply press <Enter>, or
go back to another mode.

.. _using_virtaal#quality_checks_mode:

Quality checks mode
-------------------

.. versionadded:: 0.7

In the “Quality checks” navigation mode, you can select certain quality checks
from the list of possible issues seen by Virtaal. For more information, visit
the :doc:`quality checks <checks>` page.

.. _using_virtaal#privacy_issues:

Privacy issues
==============

Commercial users of Virtaal should be aware of certain privacy issues:

.. _using_virtaal#virtaals_log_file:

Virtaal's log file
------------------

A record of some of the source text and matches served are kept on the local
computer in a file called virtaal_log.txt (on Windows XP machines, this file
may be found in Application Data\Virtaal).  The log file is not deleted when a
file is closed in Virtaal or when Virtaal exists.  The file can be safely
deleted manually.

.. _using_virtaal#virtaals_local_tm:

Virtaal's local TM
------------------

All translated segments of any file opened, edited and saved in Virtaal are
added to Virtaal's local translation memory (TM) in a file called tm.db (on
Windows XP machines, this file may be found in Application Data\Virtaal).  The
TM is not purged or deleted when Virtaal exists, and the TM file can only have
the name "tm.db".

The consequences are that (a) your translation remains on the local machine and
(b) translations from all previous texts are served as matches for all future
texts.

It is safe to delete and/or rename the file.

.. _using_virtaal#network_based_translation_memory:

Network based Translation Memory
--------------------------------

If you have the appropriate plugins enabled, Virtaal will deliver results from
network based translation memories. Since the source text is sent to the
service provider, take care that you are allowed to do that. In the case where
the source text is confidential, this is probably not a good idea.

.. _using_virtaal#contributions_to_remote_tms:

Contributions to remote TMs
---------------------------

Although Virtaal may query remote translation memories such as the online TM
Open-Tran, none of your own translations are automatically uploaded or
contributed to a public or remote TM.  The only way you can contribute your
translations to a public or remote TM is to send the PO file yourself, for
example via e-mail.

.. _using_virtaal#user_information_in_po_files:

User information in PO files
----------------------------

The first time you use Virtaal, you'll be prompted for your name, mail address
and team information.  This information is then added to all PO files you
translate in future.  If a PO file already has an author, its author will be
commented out and your name will be added as the current author.  PO files from
opensource projects are often made public, and the details you entered into
Virtaal (your name and mail address) may subsequently become available to spam
harvesters and search engines, in clear text.

.. _using_virtaal#network_based_machine_translation:

Network based Machine Translation
---------------------------------

If you have the appropriate plugins enabled, Virtaal will deliver results from
network based machine translation engines. Since the source text is sent to the
service provider, take care that you are allowed to do that. In the case where
the source text is confidential, this is probably not a good idea.
