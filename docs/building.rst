
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

- `GTK+ <http://www.gtk.org/download/index.php>`_ runtime (for Windows download
  the `latest bundle <http://www.gtk.org/download/win32.php>`_)
- `PyGTK <http://pygtk.org/downloads.html>`_
- `lxml <https://pypi.python.org/pypi/lxml/>`_
- libglade and its python bindings (might be called something like
  pygtk2.0-libglade on your Linux distribution)
- Translate-toolkit (if a current enough version is packaged, it might be
  called python-translate on your Linux distribution)
- simplejson (might be called something like python-simplejson on your Linux
  distribution)
- PyCurl (might be called something like python-curl or python-pycurl on your
  Linux distribution)
- sqlite3 (only required if using Python 2.4)
- wsgiref (only required if using Python 2.4)

.. _building#optional_packages:

Optional Packages
=================

These are not build dependencies but usually improve the user experience.

- psyco -- provides a nice speedup
- Enchant, pyenchant, gtkspell and pygtkspell (might be packaged as
  gnome-python-extras or something similar) -- provides all
  :doc:`spell_checking` functionality.  For Windows:

  - See `Gramps
    <http://gramps-project.org/wiki/index.php?title=Windows_installer>`_ and
    `PyEnchant <http://pythonhosted.org/pyenchant/>`_ for Windows installers
  - While gtkspell expects libenchant.dll, copy libenchant-1.dll to the
    alternate name (setup.py expects both while this is the case)
  - Remove the .dll files of dependencies shipped with pyenchant (iconv, glib,
    gmodule, intl) -- they conflict with the ones coming from GTK but are
    picked up by setup.py for some reason

- iso-codes -- if you want translated language names
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
bin/virtaal, uncomment the line 

.. code-block:: python

   #packaged = True

by removing the hash sign. This way Virtaal can start a bit quicker with no
loss of functionality.

.. _building#windows:

Windows
=======

.. note:: For the translate-toolkit, be sure to get the Python library -- the
   one marked ``win32.exe`` -- and not the stand-alone Windows installer, which
   is labelled ``setup.exe``.  You might need to create this yourself with ::

       python setup.py bdist_wininst

   or just ensure that the Translate Toolkit is in your PYTHONPATH.

If you would like to build a stand-alone Windows installer, you will also need
to get: 

- `Py2exe <http://py2exe.org>`_
- `InnoSetup <http://www.jrsoftware.org/isinfo.php>`_

.. _building#osx:

OSX
===
This is just some notes -- it is incomplete and might be entirely off the mark.
Virtaal and all dependencies run on OSX, but we still need help to document the
simplest process, and to build installable packages.

This was tried so far on Mac OSX Tiger (10.5):

Install the "inst" directory from this disk image somewhere:
http://www.immunityinc.com/downloads/CANVAS_OSX_SUPPORT.dmg

This GTK+ port does not need X11.

add the following to the PYTHONPATH: inst/lib/python2.5/site-packages

run python bin/virtaal

If you want, get the OS X Leopard theme: http://kims-area.com/?q=node/4 Install
it into inst/share/themes/ and add an environment variable: export
GTK2_RC_FILES=inst/share/themes/OS\ X\ Leopard/gtk-2.0/gtkrc

.. image:: /_static/virtaal-osx.png

Older
-----
Older attempt, no success yet using this way:

Install the Gtk+ Mac OSX framework: http://www.gtk-osx.org/ Install pygtk and
pygobject from the GNOME FTP mirrors: ftp://ftp.gnome.org./pub/GNOME/sources/
(extract, still need to get pygobject installed)
