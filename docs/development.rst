.. _development#development:

Development
***********

Hygiene checks (pre-commit / prek)
===================================

This repo uses a `pre-commit <https://pre-commit.com>`_-format config
(``.pre-commit-config.yaml``) for basic hygiene checks - see that file
for the current list, rather than duplicating it here.

Run it with `prek <https://prek.j178.dev/>`_ - a drop-in, single-binary
reimplementation of pre-commit, no Python runtime needed to run the
checks themselves::

  brew install prek      # or: pip install prek / pipx install prek
  prek install

That installs a git hook so the checks run automatically before each
commit. ``pre-commit`` itself also still works unmodified against the
same config file, if you'd rather use that.

Copyright headers
===================

New ``.py`` files should carry the header documented in
``.license.header.txt`` at the repo root - see ``AUTHORS.md`` for the
full contributor list this points at. One of the pre-commit checks
above verifies it on every changed file that already has some header;
it doesn't require one on a file that never had one.
