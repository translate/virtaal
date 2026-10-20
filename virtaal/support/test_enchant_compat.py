#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib
import sys
import types

from virtaal.support.enchant_compat import import_enchant, self_check


def test_leftover_enchant_directory_is_not_enchant(monkeypatch, tmp_path):
    """#4313: an "enchant" directory with no __init__.py imports as an
    empty namespace package."""
    (tmp_path / 'enchant' / '__pycache__').mkdir(parents=True)
    monkeypatch.delitem(sys.modules, 'enchant', raising=False)
    # A real pyenchant anywhere on sys.path would win over the directory.
    monkeypatch.setattr(sys, 'path', [str(tmp_path)])
    importlib.invalidate_caches()
    assert import_enchant() is None


def test_missing_enchant(monkeypatch):
    monkeypatch.setitem(sys.modules, 'enchant', None)
    assert import_enchant() is None


def test_usable_enchant(monkeypatch):
    enchant = types.ModuleType('enchant')
    enchant.dict_exists = enchant.list_languages = enchant.get_user_config_dir = lambda *a: None
    monkeypatch.setitem(sys.modules, 'enchant', enchant)
    assert import_enchant() is enchant


def test_self_check_without_enchant(monkeypatch):
    monkeypatch.setitem(sys.modules, 'enchant', None)
    assert self_check('en_US') == 'enchant: none\n'
