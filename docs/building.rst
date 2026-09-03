
.. _building#building:

Building
********

To build Virtaal yourself, you will need a packaged archive of the Virtaal
source code, or obtain it directly from Git.

To get the source code direction from Git use this command::

  git clone git@github.com:translate/virtaal.git

.. _building#required_packages:

Required Packages
=================

- GTK3 and PyGObject (``python3-gi``/``gir1.2-gtk-3.0`` or similar on
  Linux, Homebrew's ``pygobject3``/``gtk+3`` on macOS, `gvsbuild
  <https://github.com/wingtk/gvsbuild>`_ on Windows) - a system
  prerequisite, not something ``pip install`` provisions on its own;
  see ``.github/workflows/ci.yml`` for exactly what each platform's CI
  job installs
- `Translate Toolkit <https://pypi.org/project/translate-toolkit/>`_
- `lxml <https://pypi.org/project/lxml/>`_
- `PyCurl <https://pypi.org/project/pycurl/>`_
- `diff_match_patch <https://pypi.org/project/diff-match-patch/>`_
- `python-Levenshtein <https://pypi.org/project/python-Levenshtein/>`_
- `cheroot <https://pypi.org/project/cheroot/>`_

The Python packages above are all declared in ``pyproject.toml`` and
installed automatically by ``pip install .`` - only GTK3/PyGObject
needs installing separately first.

.. _building#optional_packages:

Optional Packages
=================

These are not build dependencies but usually improve the user experience.

- psyco -- provides a nice speedup
- Enchant, pyenchant, gtkspell and pygtkspell (might be packaged as
  gnome-python-extras or something similar) -- provides all :doc:`spell
  checking <spell_checking>` functionality.  For Windows:

  - See `Gramps
    <http://gramps-project.org/wiki/index.php?title=Windows_installer>`_ and
    `PyEnchant <http://pythonhosted.org/pyenchant/>`_ for Windows installers
  - While gtkspell expects libenchant.dll, copy libenchant-1.dll to the
    alternate name (`setup.py` expects both while this is the case)
  - Remove the .dll files of dependencies shipped with pyenchant (iconv, glib,
    gmodule, intl) -- they conflict with the ones coming from GTK but are
    picked up by setup.py for some reason

- iso-codes -- if you want translated language names
- libproxy and its Python binding, which might be called something like
  python-libproxy on your system -- improved support for proxies on Linux
  (since Virtaal 1.0)
- The optional fts3 module for sqlite3 will be used if it is available -
  provides speedups with TM retrieval  (it is safe to just overwrite a better
  sqlite library over the one available in Python for Windows)
- libtranslate -- used by Machine Translation plugin
- psycopg2 -- for TinyTM plugin
- python-Levenshtein -- speeds up Levenshtein distance measures, if not present
  we'll use a pure Python version.

.. _building#unix:

UNIX
====

You should be able to run Virtaal from the source tree. If you would like to
install Virtaal, you can build it using ::

  ./setup.py build

and then you can install it with ::

  sudo ./setup.py install

.. _building#distribution_packagers:

Distribution Packagers
----------------------
For users running from a tarball, we do some dependency checking when starting
Virtaal to be able to give accurate error messages in case of missing
dependencies. However, if you have all of these sorted out in your package
dependencies, there is no need for Virtaal to do this any more. In the file
`bin/virtaal`, uncomment the line

.. code-block:: python

   #packaged = True

by removing the hash sign. This way Virtaal can start a bit quicker with no
loss of functionality.

.. _building#windows:

Windows
=======

Requires `gvsbuild <https://github.com/wingtk/gvsbuild>`_'s GTK3
build and `Inno Setup <https://jrsoftware.org/isinfo.php>`_, in
addition to the running-from-source prerequisites above::

  devsupport\packaging\windows\build_standalone.ps1
  devsupport\packaging\windows\build_installer.ps1

The first produces a frozen ``dist\virtaal\`` tree (PyInstaller,
one-dir mode - see that script's own comments for why not
``--onefile``); the second wraps it into a single
``virtaal-<version>-setup.exe`` via Inno Setup
(``devsupport/packaging/windows/virtaal.iss``).

.. _building#macos:

macOS
=====

A plain ``python3 -m venv`` can't see Homebrew's GTK3/PyGObject at
all - create the venv with ``--system-site-packages`` instead, after
installing the running-from-source prerequisites above via Homebrew
(``pygobject3 gtk+3 gtk-mac-integration``, plus ``enchant
gtkspell3`` for spell checking)::

  brew install pygobject3 gtk+3 gtk-mac-integration enchant gtkspell3
  python3 -m venv --system-site-packages .venv
  . .venv/bin/activate
  pip install --no-build-isolation .[test]
  python bin/virtaal

Building a distributable ``.app``/``.dmg`` uses `PyInstaller
<https://pyinstaller.org/>`_ and `dmgbuild
<https://dmgbuild.readthedocs.io/>`_ on top of the above::

  devsupport/packaging/macos/build_standalone.sh
  devsupport/packaging/macos/build_dmg.sh

The first produces ``dist/Virtaal.app`` (PyInstaller, settings in
``devsupport/packaging/macos/virtaal.spec``); the second wraps it
into ``dist/Virtaal.dmg`` (settings in
``devsupport/packaging/macos/dmgbuild-settings.py``). CI's
``build-macos-app`` job runs these same two scripts and uploads the
results as workflow artifacts on every push.
