#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os

import pytest

from virtaal.common.langpath import is_safe_lang_code, lang_folder_name, path_inside

VALID_CODES = ['af', 'pt_BR', 'sr@latin', 'zh-Hans', 'son', 'ca@valencia', 'en-GB', 'con', 'NUL', 'a' * 64]
HOSTILE_CODES = ['../x', '/abs', 'a/b', '..', '.', '', '.hidden', 'a..b',
                 'a\\b', 'C:x', '../../../../Documents/x', 'af\x00', ' af', 'af.', 'a' * 65, None, 5]


@pytest.mark.parametrize('code', VALID_CODES)
def test_is_safe_lang_code_accepts_real_codes(code):
    assert is_safe_lang_code(code)


@pytest.mark.parametrize('code', HOSTILE_CODES)
def test_is_safe_lang_code_rejects_other_codes(code):
    assert not is_safe_lang_code(code)


def test_path_inside_joins_a_name_inside_the_directory(tmp_path):
    assert path_inside(str(tmp_path), 'en__af.tbx') == os.path.join(str(tmp_path), 'en__af.tbx')


@pytest.mark.parametrize('name', ['../x', '/abs', '..', '.', '', 'a/../../x'])
def test_path_inside_rejects_a_name_leaving_the_directory(tmp_path, name):
    assert path_inside(str(tmp_path), name) is None


def test_path_inside_rejects_a_symlink_out_of_the_directory(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    try:
        (root / 'link').symlink_to(tmp_path)
    except OSError:
        pytest.skip('no symlink permission')

    assert path_inside(str(root), 'link', 'x') is None


@pytest.mark.parametrize('code, name', [
    ('con', 'con_'), ('CON', 'CON_'), ('Aux', 'Aux_'), ('nul.txt', 'nul_.txt'),
    ('com1', 'com1_'), ('LPT9', 'LPT9_'), ('prn', 'prn_'),
    ('af', 'af'), ('cons', 'cons'), ('com', 'com'), ('com0', 'com0'), ('sr@latin', 'sr@latin'),
])
def test_lang_folder_name_only_changes_windows_device_names(code, name):
    assert lang_folder_name(code) == name
