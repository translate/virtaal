#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib
import runpy
import sys
import types

import pytest

from virtaal.support.enchant_compat import import_enchant, self_check

needs_enchant = pytest.mark.skipif(import_enchant() is None, reason="pyenchant is not available")


def _gtkspell_available():
    try:
        import gi
        gi.require_version('GtkSpell', '3.0')
        from gi.repository import GtkSpell  # noqa: F401
    except (ImportError, ValueError):
        return False
    return True


def _report(text):
    return dict(line.split(': ', 1) for line in text.splitlines())


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


# What the packaged builds' smoke tests run, here against the real libraries.

@needs_enchant
def test_self_check_reports_the_enchant_library_and_providers():
    import enchant
    from enchant import _enchant

    report = _report(self_check('en_US'))

    assert report['enchant'] == _enchant.enchant_lib_path
    assert report['providers'] == ' '.join(sorted(p.name for p in enchant.Broker().describe()))
    assert report['dictionary'] == str(enchant.dict_exists('en_US'))


@needs_enchant
def test_self_check_spell_checks_with_an_installed_dictionary():
    import enchant
    if not (enchant.dict_exists('en_US') and _gtkspell_available()):
        pytest.skip("needs GtkSpell and an en_US dictionary")

    assert _report(self_check('en_US'))['gtkspell'] == 'ok'


@needs_enchant
def test_self_check_reports_a_language_without_a_dictionary():
    report = _report(self_check('xx_YY'))

    assert report['dictionary'] == 'False'
    assert report['gtkspell'] != 'ok'
    if _gtkspell_available():
        assert 'xx_YY' in report['gtkspell']


def test_run_module_prints_the_report(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, 'enchant', None)
    monkeypatch.setattr(sys, 'argv', ['enchant_compat', 'xx_YY'])
    # run_module() warns if the module is already imported.
    monkeypatch.delitem(sys.modules, 'virtaal.support.enchant_compat')

    runpy.run_module('virtaal.support.enchant_compat', run_name='__main__')

    assert capsys.readouterr().out == 'enchant: none\n'
