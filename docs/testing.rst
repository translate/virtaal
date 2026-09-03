.. _testing#testing:

Testing
*******

.. _testing#unit_tests:

The pytest Suite
=================

Real, automated, runs in CI on every push against the actively
supported Python versions - see ``.github/workflows/ci.yml``'s
``test`` job for the current matrix. Lives under
``virtaal/`` as ``test_*.py`` files next to the code they cover (e.g.
``virtaal/test/test_storemodel.py``,
``virtaal/plugins/test_spellchecker.py``), plus a couple of
``demo_*.py`` files (``virtaal/views/widgets/demo_textbox.py`` and
siblings) that are deliberately *not* picked up by pytest - those are
manual, interactive GTK demo runners predating the automated suite,
kept for hands-on widget debugging, not real coverage.

Run it the same way CI does::

  pip install --no-build-isolation .[test]
  pytest -rvxs virtaal

On Linux without a real display, wrap it in ``xvfb-run`` (CI does)::

  xvfb-run -a --server-args="-screen 0 1024x768x24" pytest -rvxs virtaal

Real translation files for manual testing live under
``devsupport/testfiles/``, one per format or scenario worth testing
directly:

* ``checks.po`` - exercises most quality checks.
* ``plurals.po``/``plurals-zero.po`` - nplurals=3 and nplurals=1
  respectively.
* ``workflow.po``/``workflow.xliff`` - between the two, covers five of
  ``WorkflowMode``'s six states.
* ``workflow.mo`` - a compiled Gettext catalog (``pocompile``), one
  translated unit; compilation itself drops untranslated/fuzzy
  entries.
* ``workflow.tmx``, ``workflow.tbx``, ``workflow.ts`` (Qt Linguist),
  ``workflow.qph`` (Qt Phrase Book), ``workflow.ftl`` (Fluent) - cover
  translate-toolkit's other supported formats beyond Gettext PO.

Add more here as a format or scenario needs its own dedicated
coverage.

.. _testing#windows_ci:

Windows CI Checks
==================

``test-windows`` runs the pytest suite above under `gvsbuild
<https://github.com/wingtk/gvsbuild>`_'s GTK3 build.
``build-windows-installer`` goes further: it builds the real frozen
``.exe`` (PyInstaller + Inno Setup, see :doc:`building`) and drives
it directly, since a packaged build can hit bugs a dev checkout
never does (missing bundled data files, frozen-mode-only code paths).

``devsupport/testing/windows/virtaal_ui_test_helpers.ps1`` provides
the Win32 plumbing this needs - launch the real ``.exe``, get a
window handle, read its geometry/title, send keystrokes, detect and
drive popup dialogs, clean up - so each check doesn't reinvent P/Invoke
boilerplate. Two checks currently use it: a basic launch-and-verify
(open a real file, confirm the process stays alive, check the frozen
build's log files for anything unexpected), and a regression check for
a real bug found this way (the main window growing wider on every
Enter-to-advance during translation - see
``virtaal/views/widgets/storetreeview.py``'s ``select_index()``).

This is CI-only tooling, not a local test harness - there's no
hands-on driver for a real Windows session.
