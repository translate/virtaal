
.. _testing#gui_tests:

GUI Tests
*********

.. note:: This page describes an out-of-date method for running automated tests
   for Virtaal. The testing framework for Virtaal will probably change into
   something entirely different. This page is only left as a reference.

.. _testing#required_packages:

Required Packages
=================

* Dogtail
* Gnome's accessibility framework

.. _testing#running_the_tests:

Running the Tests
=================

.. note:: For KDE users: You must run ``gnome-session`` before you can run any
   of the GUI tests. ``gnome-session`` might complain that another session
   manager is already running, but it will nevertheless start up the
   accessibility services which you need to run the GUI tests.

The tests are located under the directory called ``gui_tests``. Currently, the
tests must be executed from within ``gui_tests``.

.. _testing#writing_gui_tests:

Writing GUI Tests
=================

`Accerciser <https://live.gnome.org/Accerciser>`_ allows you to inspect the GUI
of a running application that was started using the Gnome at-spi framework.
Dogtail does this when it launches an application; the easiest way to do this
is to launch a Python shell. The following Python session shows the necessary
steps and the expected output::

  Python 2.5.2 (r252:60911, Apr 21 2008, 11:12:42)
  [GCC 4.2.3 (Ubuntu 4.2.3-2ubuntu7)] on linux2
  Type "help", "copyright", "credits" or "license" for more information.
  >>> from dogtail.utils import run
  Creating logfile at /tmp/dogtail/logs/log_20080516-115347_debug ...
  >>> run("./run_virtaal.py")
  Detecting distribution: Ubuntu (or derived distribution)

You will now see ``run_virtaal.py`` in Accerciser's left column. You can now
use Accerciser to find the names of various widgets which you can use to write
Dogtail tests for Virtaal.

.. _testing#external_links:

External Links
==============
- Some discussions on Dogtail:
  http://lists.freedesktop.org/archives/ldtp-dev/2006-October/000484.html

