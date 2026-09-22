#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from virtaal.common.configurable import Configurable
from virtaal.plugins.terminology.models.localfile import TerminologyModel


def _make_model(config, monkeypatch, internal_name='localfile'):
    """A TerminologyModel with a controlled self.config, bypassing the
        real on-disk terminology.ini that Configurable.load_config()
        would otherwise read/depend on."""
    monkeypatch.setattr(Configurable, 'load_config', lambda self: None)
    model = TerminologyModel.__new__(TerminologyModel)
    model.internal_name = internal_name
    model.default_config = TerminologyModel.default_config
    model.config = config
    return model


def _fake_store(units, filename=''):
    return SimpleNamespace(units=units, filename=filename)


def _fake_unit(source, target):
    return SimpleNamespace(source=source, target=target)


# get_duplicates() #

def test_get_duplicates_finds_an_exact_source_and_target_match(monkeypatch):
    model = _make_model({}, monkeypatch)
    model.stores = [_fake_store([_fake_unit('hello', 'hallo')])]

    assert model.get_duplicates('hello', 'hallo') is True


def test_get_duplicates_strips_whitespace_before_comparing(monkeypatch):
    model = _make_model({}, monkeypatch)
    model.stores = [_fake_store([_fake_unit('hello', 'hallo')])]

    assert model.get_duplicates('  hello  ', '  hallo  ') is True


def test_get_duplicates_is_false_when_only_source_matches(monkeypatch):
    model = _make_model({}, monkeypatch)
    model.stores = [_fake_store([_fake_unit('hello', 'hallo')])]

    assert model.get_duplicates('hello', 'something else') is False


def test_get_duplicates_searches_across_multiple_stores(monkeypatch):
    model = _make_model({}, monkeypatch)
    model.stores = [
        _fake_store([_fake_unit('one', 'een')]),
        _fake_store([_fake_unit('hello', 'hallo')]),
    ]

    assert model.get_duplicates('hello', 'hallo') is True


# get_units_with_source() #

def test_get_units_with_source_is_case_insensitive_and_strips_whitespace(monkeypatch):
    model = _make_model({}, monkeypatch)
    unit = _fake_unit('  Hello  ', 'hallo')
    model.stores = [_fake_store([unit])]

    assert model.get_units_with_source('hello') == [unit]


def test_get_units_with_source_returns_every_match_across_stores(monkeypatch):
    model = _make_model({}, monkeypatch)
    unit1 = _fake_unit('hello', 'hallo')
    unit2 = _fake_unit('hello', 'goeie dag')
    model.stores = [_fake_store([unit1]), _fake_store([unit2])]

    assert model.get_units_with_source('hello') == [unit1, unit2]


def test_get_units_with_source_returns_empty_list_for_no_match(monkeypatch):
    model = _make_model({}, monkeypatch)
    model.stores = [_fake_store([_fake_unit('hello', 'hallo')])]

    assert model.get_units_with_source('goodbye') == []


# get_extend_store() / get_store_for_filename() #

def test_get_extend_store_finds_the_configured_extend_file(monkeypatch):
    model = _make_model({'extendfile': '/tmp/terms.po'}, monkeypatch)
    target_store = _fake_store([], filename='/tmp/terms.po')
    model.stores = [_fake_store([], filename='/tmp/other.po'), target_store]

    assert model.get_extend_store() is target_store


def test_get_extend_store_returns_none_when_not_found(monkeypatch):
    model = _make_model({'extendfile': '/tmp/terms.po'}, monkeypatch)
    model.stores = [_fake_store([], filename='/tmp/other.po')]

    assert model.get_extend_store() is None


def test_get_store_for_filename_matches_by_absolute_path(monkeypatch):
    model = _make_model({}, monkeypatch)
    target_store = _fake_store([], filename='relative.po')
    model.stores = [target_store]

    import os
    assert model.get_store_for_filename(os.path.abspath('relative.po')) is target_store


# load_config() #

def test_load_config_keeps_only_existing_files(monkeypatch, tmp_path):
    real_file = tmp_path / 'real.po'
    real_file.write_text('')
    model = _make_model(
        {'files': '%s,%s' % (real_file, tmp_path / 'missing.po'), 'extendfile': str(real_file)},
        monkeypatch,
    )

    model.load_config()

    assert model.config['files'] == [str(real_file)]


def test_load_config_falls_back_extendfile_to_the_first_configured_file(monkeypatch, tmp_path):
    real_file = tmp_path / 'real.po'
    real_file.write_text('')
    model = _make_model(
        {'files': str(real_file), 'extendfile': str(tmp_path / 'nonexistent-extendfile.po')},
        monkeypatch,
    )

    model.load_config()

    assert model.config['extendfile'] == str(real_file)


def test_load_config_falls_back_extendfile_to_the_default_when_nothing_exists(monkeypatch, tmp_path):
    model = _make_model(
        {'files': '', 'extendfile': str(tmp_path / 'nonexistent-extendfile.po')},
        monkeypatch,
    )

    model.load_config()

    assert model.config['extendfile'] == TerminologyModel.default_config['extendfile']


def test_load_config_always_includes_extendfile_in_files(monkeypatch, tmp_path):
    real_file = tmp_path / 'real.po'
    real_file.write_text('')
    model = _make_model({'files': '', 'extendfile': str(real_file)}, monkeypatch)

    model.load_config()

    assert str(real_file) in model.config['files']
