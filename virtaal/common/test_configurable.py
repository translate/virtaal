#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os

import pytest

from virtaal.common import pan_app
from virtaal.common.configurable import Configurable


class _Thing(Configurable):
    CONFIG_FILENAME = 'things.ini'
    default_config = {'colour': 'blue'}

    def __init__(self, internal_name):
        self.internal_name = internal_name


def test_load_config_starts_from_the_default(monkeypatch, tmp_path):
    monkeypatch.setattr(pan_app, 'get_config_dir', lambda: str(tmp_path))
    thing = _Thing('thing1')

    thing.load_config()

    assert thing.config == {'colour': 'blue'}


def test_save_then_load_round_trips_through_the_named_ini_file(monkeypatch, tmp_path):
    monkeypatch.setattr(pan_app, 'get_config_dir', lambda: str(tmp_path))
    thing = _Thing('thing1')
    thing.load_config()
    thing.config['colour'] = 'red'

    thing.save_config()
    assert (tmp_path / 'things.ini').exists()

    reloaded = _Thing('thing1')
    reloaded.load_config()
    assert reloaded.config['colour'] == 'red'


def test_different_internal_names_use_separate_sections_of_the_same_file(monkeypatch, tmp_path):
    monkeypatch.setattr(pan_app, 'get_config_dir', lambda: str(tmp_path))
    thing1 = _Thing('thing1')
    thing1.load_config()
    thing1.config['colour'] = 'red'
    thing1.save_config()

    thing2 = _Thing('thing2')
    thing2.load_config()

    assert thing2.config['colour'] == 'blue'


class _PrivateThing(_Thing):
    CONFIG_FILENAME = 'secrets.ini'
    CONFIG_PRIVATE = True


@pytest.mark.skipif(os.name == 'nt', reason="POSIX file modes")
def test_a_private_config_file_is_saved_owner_only(monkeypatch, tmp_path):
    monkeypatch.setattr(pan_app, 'get_config_dir', lambda: str(tmp_path))
    (tmp_path / 'secrets.ini').write_text('')
    (tmp_path / 'secrets.ini').chmod(0o644)
    (tmp_path / 'things.ini').write_text('')
    (tmp_path / 'things.ini').chmod(0o644)
    for thing in (_PrivateThing('thing1'), _Thing('thing1')):
        thing.load_config()
        thing.save_config()

    assert (tmp_path / 'secrets.ini').stat().st_mode & 0o777 == 0o600
    assert (tmp_path / 'things.ini').stat().st_mode & 0o777 == 0o644
