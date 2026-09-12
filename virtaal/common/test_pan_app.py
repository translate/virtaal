#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os

import pytest

from virtaal.common import pan_app
from virtaal.common.pan_app import (
    _build_launch_marker,
    _open_frozen_log,
    _read_ini_recovering,
    _set_enchant_env_vars,
    _trim_log_to_last_launches,
    get_config_dir,
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


def _launch(n):
    return '=== launch 2026-09-%02d 00:00:00 | Virtaal 1.0.0-beta1 (abc%04d) ===\ncontent %d\n' % (n, n, n)


def test_trim_log_to_last_launches_keeps_only_the_tail(tmp_path):
    path = str(tmp_path / "test.log")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(_launch(n) for n in range(1, 6)))

    _trim_log_to_last_launches(path, keep=2)

    with open(path, encoding='utf-8') as f:
        kept = f.read()
    assert kept == _launch(4) + _launch(5)


def test_trim_log_to_last_launches_leaves_a_short_log_alone(tmp_path):
    path = str(tmp_path / "test.log")
    original = _launch(1) + _launch(2)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(original)

    _trim_log_to_last_launches(path, keep=2)

    with open(path, encoding='utf-8') as f:
        assert f.read() == original


def test_trim_log_to_last_launches_tolerates_a_missing_file(tmp_path):
    _trim_log_to_last_launches(str(tmp_path / "missing.log"), keep=2)  # doesn't raise


def test_get_config_dir_tolerates_a_plain_file_at_that_path(tmp_path, monkeypatch):
    # Real crash (#1427): os.makedirs() raised unhandled if the config
    # path already existed as a plain file, not a directory.
    monkeypatch.setattr(pan_app.platform, 'is_windows', False)
    monkeypatch.setattr(pan_app.platform, 'is_mac', False)
    confdir = tmp_path / ".virtaal"
    confdir.write_text("not a directory")
    monkeypatch.setattr(os.path, 'expanduser', lambda p: str(confdir) if p == '~/.virtaal' else p)

    assert get_config_dir() == str(confdir)  # doesn't raise
    assert confdir.is_file()  # left alone, not clobbered


def test_read_ini_recovering_leaves_a_valid_file_alone(tmp_path):
    path = tmp_path / "settings.ini"
    path.write_text("[general]\nlastdir = /tmp\n")

    parser = pan_app.ConfigParser.RawConfigParser()
    backup_path = _read_ini_recovering(parser, str(path))

    assert backup_path is None
    assert parser.get("general", "lastdir") == "/tmp"
    assert path.exists()


def test_read_ini_recovering_backs_up_a_corrupt_file(tmp_path):
    # Real Windows crash (#3327): a user's virtaal.ini got zero-filled,
    # raising configparser.MissingSectionHeaderError unhandled at
    # startup, before any window could even be drawn.
    path = tmp_path / "settings.ini"
    path.write_bytes(b"\x00" * 200)

    parser = pan_app.ConfigParser.RawConfigParser()
    backup_path = _read_ini_recovering(parser, str(path))

    assert backup_path == str(path) + ".broken"
    assert not path.exists()
    assert open(backup_path, 'rb').read() == b"\x00" * 200
    assert parser.sections() == []


def test_read_ini_recovering_does_not_clobber_an_existing_backup(tmp_path):
    path = tmp_path / "settings.ini"
    path.write_bytes(b"\x00" * 10)
    (tmp_path / "settings.ini.broken").write_text("earlier backup")

    parser = pan_app.ConfigParser.RawConfigParser()
    backup_path = _read_ini_recovering(parser, str(path))

    assert backup_path == str(path) + ".broken.2"


def test_settings_recovers_from_a_corrupt_virtaal_ini(tmp_path):
    path = tmp_path / "virtaal.ini"
    path.write_bytes(b"\x00" * 200)

    settings = pan_app.Settings(str(path))

    assert settings.config_recovery_backup == str(path) + ".broken"
    assert settings.config.sections() == settings.sections  # all empty, none lost


def test_open_frozen_log_trims_before_appending(tmp_path):
    path = str(tmp_path / "test.log")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(_launch(n) for n in range(1, 4)))

    f = _open_frozen_log(path)
    try:
        f.write(_launch(4))
    finally:
        f.close()

    with open(path, encoding='utf-8') as f:
        kept = f.read()
    assert kept == _launch(2) + _launch(3) + _launch(4)
