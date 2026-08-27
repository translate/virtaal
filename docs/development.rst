.. _development#development:

Development
***********

Hygiene checks (pre-commit / prek)
===================================

This repo uses a `pre-commit <https://pre-commit.com>`_-format config
(``.pre-commit-config.yaml``) for basic hygiene checks: trailing
whitespace, end-of-file newlines, valid YAML/TOML, no leftover
merge-conflict markers, no accidental large files, and a local check
that ``po/virtaal.pot`` is kept up to date with the translatable
strings it should contain.

Run it with `prek <https://prek.j178.dev/>`_ - a drop-in, single-binary
reimplementation of pre-commit, no Python runtime needed to run the
checks themselves::

  brew install prek      # or: pip install prek / pipx install prek
  prek install

That installs a git hook so the checks run automatically before each
commit. ``pre-commit`` itself also still works unmodified against the
same config file, if you'd rather use that.
