
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
:doc:`screenshots <screenshots>`.

Learn more about :doc:`using Virtaal <using_virtaal>` and some extra
:doc:`tips and tricks <tips>` for people who want to customise their
installation. Keyboard shortcuts are available from Virtaal's own
Help menu.

.. toctree::
   :maxdepth: 1
   :hidden:

   using_virtaal
   features
   screenshots
   tips
   cli_options
   releases/index

.. _index#installation:

Installation
============
Download the latest release (Windows installer, macOS `.dmg`, Linux
Flatpak) from the `Releases page <https://github.com/translate/virtaal/releases>`_.
The macOS builds need macOS 15 (Sequoia) or later.
On Linux, pick the ``.flatpak`` for your machine (``x86_64`` or
``aarch64``) and install it with::

  flatpak install --user Virtaal-linux-x86_64.flatpak

This also installs the GNOME runtime from Flathub if it's missing. The
bundle doesn't update itself: install each new release the same way.
To build from source, see :doc:`building`.

.. _index#contact:

Contact
=======
- `Report bugs <https://github.com/translate/virtaal/issues/new?template=bug_report.yml>`_
- `Suggest a feature <https://github.com/translate/virtaal/issues/new?template=feature_request.yml>`_

.. _index#contributing:

Contributing
============
There are many ways of contributing to Virtaal - sharing it with people,
writing documentation, packaging for more platforms, or contributing code
via `GitHub <https://github.com/translate/virtaal>`_ (see
`CONTRIBUTING.md <https://github.com/translate/virtaal/blob/main/CONTRIBUTING.md>`_).

If you would like to contribute to the Virtaal software, you can start by
reading the instructions on the following pages:

.. toctree::
   :maxdepth: 1

   localising_virtaal
   building
   testing
   development
   development_plans
