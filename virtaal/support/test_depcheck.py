#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.support import depcheck

# test_import()

def test_import_returns_true_for_a_real_module():
    assert depcheck.test_import('os') is True


def test_import_returns_false_for_a_missing_module():
    assert depcheck.test_import('no_such_module_xyz') is False


# test_sqlite3_version() / test_json(): real stdlib modules, always
# available in any environment these tests run in.

def test_sqlite3_version_is_met():
    assert depcheck.test_sqlite3_version() is True


def test_json_is_met():
    assert depcheck.test_json() is True


# test_translate_toolkit_version()

def test_translate_toolkit_version_is_met_by_the_installed_version():
    assert depcheck.test_translate_toolkit_version() is True


def test_translate_toolkit_version_fails_below_the_minimum(monkeypatch):
    from translate import __version__
    monkeypatch.setattr(__version__, 'ver', (0, 0, 1))

    assert depcheck.test_translate_toolkit_version() is False


def test_translate_toolkit_version_fails_gracefully_if_unimportable(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == 'translate.__version__':
            raise ImportError('boom')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', fake_import)

    assert depcheck.test_translate_toolkit_version() is False


# test_gtk_version()

def test_gtk_version_is_met_by_the_installed_version():
    assert depcheck.test_gtk_version() is True


def test_gtk_version_fails_below_the_minimum(monkeypatch):
    monkeypatch.setattr(depcheck, 'MIN_GTK_VERSION', (999, 0, 0))

    assert depcheck.test_gtk_version() is False


# check_dependencies(): dispatches to extra_tests when a module has a
# real version check, falls back to a plain import check otherwise.

def test_check_dependencies_returns_nothing_when_everything_passes(monkeypatch):
    monkeypatch.setattr(depcheck, 'extra_tests', {'sqlite3': lambda: True})

    assert depcheck.check_dependencies(['os', 'sqlite3']) == []


def test_check_dependencies_reports_a_failing_plain_import():
    assert depcheck.check_dependencies(['os', 'no_such_module_xyz']) == ['no_such_module_xyz']


def test_check_dependencies_reports_a_failing_extra_test(monkeypatch):
    monkeypatch.setattr(depcheck, 'extra_tests', {'gtk': lambda: False})

    assert depcheck.check_dependencies(['os', 'gtk']) == ['gtk']


def test_check_dependencies_prefers_the_extra_test_over_a_plain_import():
    # "gtk" itself isn't importable as a bare module name under gi/PyGObject
    # (test_gtk_version() is what actually probes it) - if check_dependencies
    # ever fell back to a plain import for it, this would wrongly fail.
    assert depcheck.check_dependencies(['gtk']) == []
