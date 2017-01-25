
.. _index#virtaal:

Virtaal
*******

.. image::  /_static/virtaal_logo.png
   :alt: Virtaal logo
   :align: right

Virtaal is a graphical translation tool. It is meant to be easy to use and
powerful at the same time. Although the initial focus is on software
translation (localisation or l10n), we definitely intend it to be useful for
several purposes.

Virtaal is built on the powerful API of the `Translate Toolkit
<http://toolkit.translatehouse.org>`_. "Virtaal" is an Afrikaans play on words
meaning "For Language", but also refers to translation.

Read more about the :doc:`features <features>` in Virtaal, or view the
:doc:`screenshots <screenshots>`.  You can also download a `screencast
<http://l10n.mozilla-community.org/pootle/screencasts/virtaal-0.3.ogv>`_ (33MB,
Ogg Theora format) to see some of these features in action.

Learn more about :doc:`using Virtaal <using_virtaal>`, available
:doc:`shortcuts <cheatsheet>` and some extra :doc:`tips and tricks <tips>` for
people who want to customise their installation.

.. toctree::
   :maxdepth: 1
   :hidden:

   using_virtaal
   features
   screenshots
   cheatsheet
   tips

.. _index#installation:

Installation
============
.. toctree::
   :maxdepth: 1
   :hidden:

   fedora_custom_repo

+-----------------+--------------------------------------------------------------+---------------------------------------------+
| Platform        | Instructions                                                 |  Notes                                      |
+=================+==============================================================+=============================================+
| Windows         | `Download Virtaal setup.exe                                  | Includes all dependencies                   |
|                 | <http://sourceforge.net/projects/translate/files/Virtaal/>`_ |                                             |
+-----------------+--------------------------------------------------------------+---------------------------------------------+
| Mac OS X        | `Download Virtaal .dmg                                       | Beta release. OS X 10.5 and greater         |
|                 | <http://sourceforge.net/projects/translate/files/Virtaal/>`_ |                                             |
+-----------------+--------------------------------------------------------------+---------------------------------------------+
| Ubuntu          | `Translate.org.za Tools PPA                                  | Also available in software center           |
|                 | <https://launchpad.net/~translate.org.za/+archive/ppa>`_     |                                             |
+-----------------+--------------------------------------------------------------+---------------------------------------------+
| Fedora          | yum install virtaal                                          | Or use the graphical package manager.       |
|                 |                                                              | For older Fedora releases use the           |
|                 |                                                              | :doc:`custom repo <fedora_custom_repo>`     |
+-----------------+--------------------------------------------------------------+---------------------------------------------+
| Mandriva        | urpmi virtaal                                                | Or simply use the graphical package manager |
+-----------------+--------------------------------------------------------------+---------------------------------------------+
| Debian Squeeze  | apt-get install virtaal                                      | Or simply use the graphical package manager |
+-----------------+--------------------------------------------------------------+---------------------------------------------+
| openSUSE        | zypper install virtaal                                       | Or simply use the graphical package manager |
+-----------------+--------------------------------------------------------------+---------------------------------------------+
| Other           | `Download source .zip or .tar.bz2                            | Make sure you have all the dependencies     |
|                 | <http://sourceforge.net/projects/translate/files/Virtaal>`_  | including the latest Translate Toolkit      |
+-----------------+--------------------------------------------------------------+---------------------------------------------+

.. _index#contact:

Contact
=======
- Chat in our `channel <https://gitter.im/translate/pootle>`_
- `Report bugs <https://github.com/translate/virtaal/issues/new>`_
- Join the `Translate-devel mailing list
  <https://lists.sourceforge.net/lists/listinfo/translate-devel>`_

.. _index#contributing:

Contributing
============
There are many ways of contributing to Virtaal. Join the mailing list or IRC
channel to join our effort. You can join our effort to distribute Virtaal by
sharing informing with people, writing documentation or packaging for more
platforms.

If you would like to contribute to the Virtaal software, you can start by
reading the instructions on the following pages:

.. toctree::
   :maxdepth: 1

   localising_virtaal
   building
   testing
   development_plans
   suggestions
