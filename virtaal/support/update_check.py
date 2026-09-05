#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

"""Checks GitHub for a newer release than the one currently running.

Uses the plural /releases list endpoint (newest first), not the
singular /releases/latest one - GitHub defines "latest" as the newest
non-prerelease release, which returns nothing at all while every
published release is still beta/rc-flagged. The whole point of this
check right now is surfacing newer *prereleases* to beta testers.
"""

import json
import logging
import re

from virtaal.support.httpclient import HTTPClient

RELEASES_API_URL = 'https://api.github.com/repos/translate/virtaal/releases'

_VERSION_RE = re.compile(
    r'^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)'
    r'(?:-(?P<pretype>alpha|beta|rc)(?P<prenum>\d*))?$'
)
_PRE_ORDER = {'alpha': 0, 'beta': 1, 'rc': 2}


def _parse_version(version_string):
    """Parse a plain vMAJOR.MINOR.PATCH[-alpha|beta|rcN] string into a
        tuple that sorts correctly - a release with no pre-release
        suffix always sorts after any pre-release of the same core
        version (pre-rank 99), and alpha < beta < rc for same-numbered
        pre-releases. Raises ValueError on anything else, rather than
        guessing - see is_newer()'s own fail-closed handling of that."""
    match = _VERSION_RE.match(version_string.strip())
    if not match:
        raise ValueError('unrecognised version string: %r' % (version_string,))
    core = (int(match.group('major')), int(match.group('minor')), int(match.group('patch')))
    pretype = match.group('pretype')
    if pretype is None:
        return core + (99, 0)
    prenum = int(match.group('prenum') or 0)
    return core + (_PRE_ORDER[pretype], prenum)


def is_newer(remote_version, local_version):
    """Whether remote_version is a newer release than local_version."""
    try:
        return _parse_version(remote_version) > _parse_version(local_version)
    except ValueError:
        # Either string didn't match this project's own version scheme -
        # fail closed rather than guess, never claim an update exists
        # from data we can't actually parse.
        return False


class UpdateChecker:
    """Checks once, asynchronously, whether a newer release exists than
        local_version - calling on_update_available(tag_name, html_url)
        if so. Silent (just logs) on any failure: network errors must
        never surface as an application error to the user."""

    def __init__(self, local_version, on_update_available):
        self.local_version = local_version
        self.on_update_available = on_update_available
        self._client = HTTPClient()

    def check(self):
        self._client.set_virtaal_useragent()
        self._client.get(RELEASES_API_URL, self._on_success, error_callback=self._on_error)

    def _on_success(self, _request, result):
        try:
            releases = json.loads(result.decode('utf-8'))
            latest = releases[0]
            tag_name = latest['tag_name']
            html_url = latest['html_url']
        except (ValueError, KeyError, IndexError, UnicodeDecodeError) as e:
            # ValueError covers both json.loads() and int() failures;
            # IndexError is an empty releases list (nothing published
            # yet) - all equally "nothing to report", not errors worth
            # surfacing to the user.
            logging.debug('update check: could not use response: %s' % (e,))
            return
        if is_newer(tag_name, self.local_version):
            self.on_update_available(tag_name, html_url)

    def _on_error(self, _request, status):
        logging.debug('update check: request failed, status=%r' % (status,))
