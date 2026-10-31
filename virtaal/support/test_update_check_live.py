#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Runs the update check against GitHub's live releases API (#4660).
Skipped unless VIRTAAL_LIVE_SERVICES=1."""

import os

import pytest
from gi.repository import GLib

from virtaal.support.update_check import UpdateChecker, _parse_version

pytestmark = pytest.mark.skipif(
    os.environ.get('VIRTAAL_LIVE_SERVICES') != '1',
    reason="set VIRTAAL_LIVE_SERVICES=1 to query GitHub's releases API")


def test_an_old_version_hears_about_the_latest_release():
    found, errors = [], []
    loop = GLib.MainLoop()
    checker = UpdateChecker('0.0.1', lambda *args: (found.append(args), loop.quit()))
    checker._on_error = lambda request, status: (errors.append(status), loop.quit())
    GLib.timeout_add_seconds(30, loop.quit)
    checker.check()
    loop.run()

    assert not errors, 'the releases API answered HTTP %s' % errors[0]
    assert found, 'no update reported for 0.0.1 within 30 s'
    tag_name, html_url, _asset_url = found[0]
    _parse_version(tag_name)
    assert html_url == 'https://github.com/translate/virtaal/releases/tag/' + tag_name
