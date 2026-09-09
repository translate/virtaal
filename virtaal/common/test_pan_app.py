#
# Copyright 2026 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import os

import pytest

from virtaal.common import pan_app
from virtaal.common.pan_app import (
    _build_launch_marker,
    _open_frozen_log,
    _set_enchant_env_vars,
)


def test_build_launch_marker_includes_version(monkeypatch):
    monkeypatch.setattr(pan_app, 'version_string', lambda: '1.0.0-beta1 (5bb637f)')
    marker = _build_launch_marker('2026-09-07 22:00:00')
    assert marker == '=== launch 2026-09-07 22:00:00 | Virtaal 1.0.0-beta1 (5bb637f) ===\n'


def test_set_enchant_env_vars_points_at_bundled_dylib(monkeypatch):
    # _set_enchant_env_vars() writes os.environ directly (setdefault, not
    # monkeypatch) - real spellchecker-using tests elsewhere in the suite
    # would pick up these bogus paths for the rest of the process if left
    # behind, so this can't rely on monkeypatch's own auto-cleanup alone.
    for key in ('PYENCHANT_LIBRARY_PATH', 'ENCHANT_MODULE_DIR', 'ENCHANT_DATA_DIR'):
        monkeypatch.delenv(key, raising=False)
    enchant_dir = os.path.join('Some', 'App.app', 'Contents', 'Resources', 'enchant_intel')
    try:
        _set_enchant_env_vars(enchant_dir)
        assert os.environ['PYENCHANT_LIBRARY_PATH'] == \
            os.path.join(enchant_dir, 'lib', 'libenchant.1.dylib')
        assert os.environ['ENCHANT_MODULE_DIR'] == \
            os.path.join(enchant_dir, 'lib', 'enchant')
        assert os.environ['ENCHANT_DATA_DIR'] == \
            os.path.join(enchant_dir, 'share', 'enchant')
    finally:
        for key in ('PYENCHANT_LIBRARY_PATH', 'ENCHANT_MODULE_DIR', 'ENCHANT_DATA_DIR'):
            os.environ.pop(key, None)


def test_open_frozen_log_survives_characters_a_locale_codepage_cant(tmp_path):
    """Real Windows crash: the frozen build's stdout/stderr log used to
    open with no explicit encoding, defaulting to the system locale's
    codepage (e.g. cp1252) - logging.debug() writing a check-failure
    message containing "≠" (U+2260) raised UnicodeEncodeError from
    inside the logging call itself."""
    message = "Different capitalization ≠ expected\n"

    # Confirm this is a real failure mode, not a hypothetical one - the
    # exact codepage the original crash's own traceback named.
    with pytest.raises(UnicodeEncodeError):
        message.encode('cp1252')

    path = str(tmp_path / "test.log")
    f = _open_frozen_log(path)
    try:
        f.write(message)
    finally:
        f.close()

    with open(path, encoding='utf-8') as f:
        assert message in f.read()
