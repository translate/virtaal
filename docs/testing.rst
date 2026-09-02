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
``devsupport/testfiles/`` - ``checks.po`` (exercises most quality
checks), ``plurals.po``/``plurals-zero.po`` (nplurals=3 and nplurals=1
respectively), and others added as specific bugs were found and fixed.
