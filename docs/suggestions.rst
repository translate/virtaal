
.. _suggestions#suggestions:

Suggestions
***********
Listed on this page are suggestions to improve Virtaal. While you can add your
ideas here, it will probably eventually have to make its way into bugzilla for
easier tracking of things.

.. _suggestions#functionality:

Functionality
=============
- <del>Add a Welcome Page that is shown when Virtaal is run without immediately
  opening a file.</del> -- Implemented in Virtaal 0.6
- Fail well depending on how the program was launched.  From the command line
  fail by placing a message on the command line and don't go graphical.  If
  someone clicks on a file and we launch because of mime type association then
  give the error graphically and probably leave the application open.  Might be
  as simple as adding a --gui option.
- Allow the translator to add comments
- <del>Provide the ability to save files in a different format, eg. save MO
  files to PO, and vice versa.</del> -- Exporting .po to .mo implemented in
  Virtaal 0.7

.. _suggestions#gui:

GUI
===
- When selecting a unit, select the translated text so that it can be
  overwritten. -- is this a good idea, I would rather see fuzzy units
  highlighted, translated left unhighlighted and :kbd:`Ctrl+A` able to select
  all text DB.
- <del>Check that row hints work in Windows.</del>
- <del>Add syntax highlighting for the active unit's source text.</del>
- Make more attractive:

  - <del>Add borders to source and target text views.</del>
  - Make modes more distinctive.
  - Change background color of unit editor to make it stand out.
  - Improve syntax highlighting so that translatable text is more
    distinguishable.
  - Change display of suggestions (pop-up?) -- yuch no popups please, I think my
    idea is harder though, I'd like to see it like call tip that you can
    highlight and select when you go to that unit DB.
  - Smooth scrolling -- I'd include the jitter you see as you go
    :kbd:`Ctrl+Down` DB.
  - Add margins at the sides of the main window.

- Show number of translated, untranslated and fuzzy units in the status bar
- Display the unit number and give an option to go directly to a certain unit
  #.
- The TAB key for autocompletion might be counter-intuitive to some people (it
  definitely is to me). Maybe it should be changed to something else, like
  :kbd:`Ctrl+Space`, or maybe even modifiable by the user.
- Change keys used to select/copy placeables. The hand movement required to
  move to the arrows are very disruptive. But to what should it be changed?
- <del>Rename "Fuzzy"? A tester suggested that the term might be very confusing
  to new users.</del> -- "fuzzy" almost entirely gone since Virtaal 0.7
