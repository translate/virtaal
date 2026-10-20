#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import hashlib
import importlib.util
import os

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "devsupport", "packaging", "check_release_assets.py")

# Enough of each format's header (and a dmg's trailer) for kind_problem().
CONTENT = {
    'exe': b'MZ' + b'\0' * 62,
    'dmg': b'\0' * 600 + b'koly' + b'\0' * 508,
    'zip': b'PK\x03\x04' + b'\0' * 60,
}


def _flatpak(arch):
    return b'flatpak\0\x01\0\0\0ref\0\0\0\0\0app/io.github.translate.Virtaal/%s/stable' % arch.encode()


def _appimage(arch):
    machine = {'x86_64': b'\x3e\x00', 'aarch64': b'\xb7\x00'}[arch]
    return b'\x7fELF\x02\x01\x01\0AI\x02' + b'\0' * 7 + machine + b'\0' * 44


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location("check_release_assets", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _content(name):
    if name.endswith('.flatpak'):
        return _flatpak('aarch64' if 'aarch64' in name else 'x86_64')
    if name.endswith('.AppImage'):
        return _appimage('aarch64' if 'aarch64' in name else 'x86_64')
    return CONTENT[name.rsplit('.', 1)[1]]


def _release(check, tag, prerelease=True, content=_content, **overrides):
    assets = []
    for name in check.expected_assets(tag):
        data = content(name)
        asset = {'name': name, 'size': len(data), 'digest': 'sha256:' + hashlib.sha256(data).hexdigest()}
        asset.update(overrides.get(name, {}))
        assets.append(asset)
    return {'prerelease': prerelease, 'draft': False, 'assets': assets}


def test_expected_assets_for_a_release_candidate(check):
    assert check.expected_assets('v1.0.0-rc2') == [
        'virtaal-1.0.0-rc2-setup.exe',
        'Virtaal-macos-arm64.dmg', 'Virtaal-macos-x86_64.dmg',
        'Virtaal-linux-x86_64.flatpak', 'Virtaal-linux-aarch64.flatpak',
        'Virtaal-linux-x86_64.AppImage', 'Virtaal-linux-aarch64.AppImage',
        'virtaal-translation-packs-v1.0.0-rc2.zip',
    ]


def test_expected_assets_for_a_final_release_have_no_translation_packs(check):
    names = check.expected_assets('v1.0.0')
    assert 'virtaal-1.0.0-setup.exe' in names
    assert not any('translation-packs' in name for name in names)


def test_a_complete_release_has_no_problems(check):
    assert check.release_problems('v1.0.0-rc2', _release(check, 'v1.0.0-rc2')) == []


def test_release_problems_lists_missing_empty_and_undigested_assets(check):
    release = _release(check, 'v1.0.0-rc2', **{
        'Virtaal-macos-arm64.dmg': {'size': 0},
        'Virtaal-macos-x86_64.dmg': {'digest': None},
    })
    release['assets'] = [a for a in release['assets'] if a['name'] != 'Virtaal-linux-aarch64.AppImage']
    release['assets'].append({'name': 'stray.txt', 'size': 3, 'digest': 'sha256:x'})

    assert check.release_problems('v1.0.0-rc2', release) == [
        'Virtaal-macos-arm64.dmg: empty',
        'Virtaal-macos-x86_64.dmg: GitHub recorded no sha256 digest',
        'Virtaal-linux-aarch64.AppImage: missing',
        'stray.txt: not expected for v1.0.0-rc2',
    ]


@pytest.mark.parametrize('tag, prerelease', [('v1.0.0-rc2', False), ('v1.0.0', True)])
def test_release_problems_checks_the_prerelease_flag(check, tag, prerelease):
    problems = check.release_problems(tag, _release(check, tag, prerelease=prerelease))
    assert len(problems) == 1 and problems[0].startswith('marked ')


def test_kind_problem_accepts_each_format(check, tmp_path):
    for name in check.expected_assets('v1.0.0-rc2'):
        path = tmp_path / name
        path.write_bytes(_content(name))
        assert check.kind_problem(name, str(path)) is None, name


@pytest.mark.parametrize('name, data', [
    ('Virtaal-macos-arm64.dmg', b'<html>error</html>'),
    ('Virtaal-linux-aarch64.AppImage', _appimage('x86_64')),
    ('Virtaal-linux-x86_64.flatpak', _flatpak('aarch64')),
    ('virtaal-1.0.0-setup.exe', b'PK\x03\x04'),
])
def test_kind_problem_rejects_the_wrong_file(check, tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    assert check.kind_problem(name, str(path))


def _fake_download(content=_content):
    seen = []

    def download(tag, repo, name, folder):
        path = os.path.join(folder, name)
        with open(path, 'wb') as f:
            f.write(content(name))
        seen.append(path)
        return path
    return download, seen


def test_check_files_verifies_and_deletes_every_download(check):
    download, seen = _fake_download()

    problems = check.check_files('v1.0.0-rc2', 'repo', _release(check, 'v1.0.0-rc2'), downloader=download)

    assert problems == []
    assert len(seen) == 8
    assert not any(os.path.exists(path) for path in seen)
    assert not os.path.exists(os.path.dirname(seen[0]))


def test_check_files_reports_a_digest_that_doesnt_match(check):
    release = _release(check, 'v1.0.0-rc2')
    download, _ = _fake_download(lambda name: _content(name) + (b'x' if name.endswith('.zip') else b''))

    problems = check.check_files('v1.0.0-rc2', 'repo', release, downloader=download)

    assert len(problems) == 1
    assert problems[0].startswith('virtaal-translation-packs-v1.0.0-rc2.zip: sha256 ')


def test_check_files_cleans_up_when_a_check_raises(check, monkeypatch):
    download, seen = _fake_download()
    monkeypatch.setattr(check, 'sha256', lambda path: (_ for _ in ()).throw(KeyboardInterrupt))

    with pytest.raises(KeyboardInterrupt):
        check.check_files('v1.0.0-rc2', 'repo', _release(check, 'v1.0.0-rc2'), downloader=download)

    assert not os.path.exists(os.path.dirname(seen[0]))


def test_main_exits_1_on_a_problem(check, monkeypatch):
    release = _release(check, 'v1.0.0-rc2', prerelease=False)
    monkeypatch.setattr(check, 'fetch_release', lambda tag, repo: release)

    assert check.main(['v1.0.0-rc2', '--no-download']) == 1


def test_main_exits_0_for_a_good_release(check, monkeypatch):
    release = _release(check, 'v1.0.0-rc2')
    monkeypatch.setattr(check, 'fetch_release', lambda tag, repo: release)
    monkeypatch.setattr(check, 'check_files', lambda tag, repo, release: [])

    assert check.main(['v1.0.0-rc2']) == 0
