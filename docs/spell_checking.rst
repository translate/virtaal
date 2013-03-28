
.. _spell_checking#spell_checking:

Spell Checking
**************
Virtaal provides spell checking for translators to see possible typing and
spelling mistakes.  Where the relevant spell checkers are available, it will be
enabled for both the source and target text.  Possible misspellings will be
underlined in red, and the context menu could provide suggestions and the
ability to add it to the personal word list.

.. _spell_checking#windows:

Windows
=======

.. versionadded:: 0.7

Currently only Hunspell and Myspell spell checkers are supported.  You need to
install spell checkers for the languages that you are interested in.

Copy the .aff and .dic files into  Application Data\enchant\myspell\  for your
account.  If you are the Administrator user, that could be in C:\Documents and
Settings\Administrator\Application Data\enchant\myspell\

.. _spell_checking#linux:

Linux
=====
On Linux systems, you need to have the following packages installed:

- enchant
- pyenchant
- gtkspell
- pygtkspell (might be packaged as gnome-python-extras or something similar)
- Spell checkers for the languages that you are interested in (all checkers
  supported by your enchant installation should be usable)

