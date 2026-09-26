#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Tests for update_check's logic that's cheaply, deterministically
testable without an actual network call - version comparison, asset
matching, and _on_success()'s parsing of an already-fetched response."""

import json

import pytest

from virtaal.common.platform import Platform
from virtaal.support import update_check
from virtaal.support.update_check import UpdateChecker, find_asset_url, is_newer


@pytest.mark.parametrize("remote,local,expected", [
    # Same core version, different beta numbers - the main case that
    # matters while every published release is still a prerelease.
    ("v1.0.0-beta2", "1.0.0-beta1", True),
    ("v1.0.0-beta1", "1.0.0-beta2", False),
    ("v1.0.0-beta1", "1.0.0-beta1", False),
    # A stable release outranks any prerelease of the same core version.
    ("v1.0.0", "1.0.0-beta5", True),
    ("v1.0.0-rc1", "1.0.0", False),
    # alpha < beta < rc for the same core version.
    ("v1.0.0-rc1", "1.0.0-beta9", True),
    ("v1.0.0-beta1", "1.0.0-alpha9", True),
    # Plain core-version ordering.
    ("v1.1.0", "1.0.0", True),
    ("v2.0.0", "1.9.9", True),
    ("v1.0.0", "1.0.1", False),
    # A leading "v" on either side shouldn't matter.
    ("1.0.1", "v1.0.0", True),
])
def test_is_newer(remote, local, expected):
    assert is_newer(remote, local) is expected


def test_is_newer_unparseable_fails_closed():
    """Malformed input never claims an update exists - fail closed,
        not guess."""
    assert is_newer("not-a-version", "1.0.0") is False
    assert is_newer("v1.0.0", "not-a-version") is False
    assert is_newer("", "1.0.0") is False


# find_asset_url() - matches ci.yml's real release job asset names
# (confirmed live against the actual v1.0.0-beta3 release).

_REAL_ASSETS = [
    {'name': 'virtaal-1.0.0-beta3-setup.exe',
     'browser_download_url': 'https://github.com/translate/virtaal/releases/download/v1.0.0-beta3/virtaal-1.0.0-beta3-setup.exe'},
    {'name': 'Virtaal-macos-arm64.dmg',
     'browser_download_url': 'https://github.com/translate/virtaal/releases/download/v1.0.0-beta3/Virtaal-macos-arm64.dmg'},
    {'name': 'Virtaal-macos-x86_64.dmg',
     'browser_download_url': 'https://github.com/translate/virtaal/releases/download/v1.0.0-beta3/Virtaal-macos-x86_64.dmg'},
]


def test_find_asset_url_windows():
    plat = Platform(os_name='nt', sys_platform='win32')
    assert find_asset_url(_REAL_ASSETS, plat) == \
        'https://github.com/translate/virtaal/releases/download/v1.0.0-beta3/virtaal-1.0.0-beta3-setup.exe'


def test_find_asset_url_mac_arm64():
    plat = Platform(os_name='posix', sys_platform='darwin', machine='arm64')
    assert find_asset_url(_REAL_ASSETS, plat) == \
        'https://github.com/translate/virtaal/releases/download/v1.0.0-beta3/Virtaal-macos-arm64.dmg'


def test_find_asset_url_mac_x86_64():
    plat = Platform(os_name='posix', sys_platform='darwin', machine='x86_64')
    assert find_asset_url(_REAL_ASSETS, plat) == \
        'https://github.com/translate/virtaal/releases/download/v1.0.0-beta3/Virtaal-macos-x86_64.dmg'


def test_find_asset_url_linux_has_no_asset_to_pick():
    """Linux ships as a Flatpak, never a direct release asset - see
        build-flatpak in ci.yml, which never publishes to a release."""
    plat = Platform(os_name='posix', sys_platform='linux', machine='x86_64')
    assert find_asset_url(_REAL_ASSETS, plat) is None


def test_find_asset_url_mac_unrecognised_arch_has_no_match():
    plat = Platform(os_name='posix', sys_platform='darwin', machine='riscv64')
    assert find_asset_url(_REAL_ASSETS, plat) is None


def test_find_asset_url_missing_expected_asset_returns_none():
    plat = Platform(os_name='nt', sys_platform='win32')
    assert find_asset_url([], plat) is None


# UpdateChecker._on_success() - parsing an already-fetched response,
# no real network call involved.

def _releases_payload(tag_name='v1.0.0-beta3', assets=_REAL_ASSETS):
    return json.dumps([{
        'tag_name': tag_name,
        'html_url': 'https://github.com/translate/virtaal/releases/tag/' + tag_name,
        'assets': assets,
    }]).encode('utf-8')


def test_on_success_calls_back_with_the_matching_asset_url(monkeypatch):
    monkeypatch.setattr(update_check.platform, 'is_windows', True)
    monkeypatch.setattr(update_check.platform, 'is_mac', False)
    calls = []
    checker = UpdateChecker('1.0.0-beta1', lambda *args: calls.append(args))

    checker._on_success(None, _releases_payload())

    assert calls == [(
        'v1.0.0-beta3',
        'https://github.com/translate/virtaal/releases/tag/v1.0.0-beta3',
        'https://github.com/translate/virtaal/releases/download/v1.0.0-beta3/virtaal-1.0.0-beta3-setup.exe',
    )]


def test_on_success_does_nothing_when_not_newer():
    calls = []
    checker = UpdateChecker('1.0.0-beta3', lambda *args: calls.append(args))

    checker._on_success(None, _releases_payload())

    assert calls == []
