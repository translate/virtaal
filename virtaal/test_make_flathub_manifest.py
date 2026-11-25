#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os
import re

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "devsupport", "packaging", "flatpak", "make_flathub_manifest.py")


@pytest.fixture(scope="module")
def make():
    spec = importlib.util.spec_from_file_location("make_flathub_manifest", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_writes_the_manifest_with_a_git_source_and_the_files_it_refers_to(make, tmp_path):
    make.main(['--commit', 'abc1234', '--tag', 'v1.0.0', str(tmp_path)])

    manifest = (tmp_path / 'io.github.translate.Virtaal.yml').read_text()
    assert 'type: dir' not in manifest
    assert 'skip:' not in manifest
    assert ('      - type: git\n'
            '        url: https://github.com/translate/virtaal.git\n'
            '        tag: v1.0.0\n'
            '        commit: abc1234\n') in manifest
    for name in make.EXTRA_FILES:
        assert (tmp_path / name).is_file()


def test_every_file_the_manifest_refers_to_is_copied(make):
    manifest = (make.HERE / make.MANIFEST).read_text()
    referenced = set(re.findall(r'^\s*(?:- |path: )([\w.-]+\.(?:ya?ml|json|patch))\s*$', manifest, re.M))

    assert referenced == set(make.EXTRA_FILES)


MODULE = ('    build-commands:\n'
          '      - pip3 install --prefix=${FLATPAK_DEST} .\n'
          '    sources:\n      - type: dir\n        path: ../../..\n')


def test_the_tag_is_optional(make):
    text = make.flathub_manifest(MODULE, 'abc1234')

    assert 'tag:' not in text
    assert 'commit: abc1234' in text


def test_the_commit_is_written_for_the_about_dialog_before_the_install(make):
    # #4991: a git source has no .git, so About showed "(unknown)".
    text = make.flathub_manifest(MODULE, 'abc1234')

    assert ('      - echo \'commit = "abc1234"\' > virtaal/_build_info.py\n'
            '      - pip3 install ') in text


def test_the_real_manifest_gets_the_commit_line(make, tmp_path):
    make.main(['--commit', 'abc1234', str(tmp_path)])

    manifest = (tmp_path / 'io.github.translate.Virtaal.yml').read_text()
    assert manifest.count('> virtaal/_build_info.py') == 1
    assert '      - echo \'commit = "abc1234"\' > virtaal/_build_info.py\n' in manifest


@pytest.mark.parametrize('commit', ['abc12', 'ABC1234', 'abc123; rm -rf /', 'v1.0.0'])
def test_a_commit_that_isnt_a_hash_is_refused(make, commit):
    with pytest.raises(ValueError):
        make.flathub_manifest(MODULE, commit)


def test_a_manifest_without_the_install_command_is_refused(make):
    with pytest.raises(ValueError):
        make.flathub_manifest('    sources:\n      - type: dir\n        path: ../../..\n', 'abc1234')


def test_a_manifest_without_the_local_source_is_refused(make):
    with pytest.raises(ValueError):
        make.flathub_manifest('modules: []\n', 'abc1234')
