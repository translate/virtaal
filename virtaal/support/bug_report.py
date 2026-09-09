#!/usr/bin/env python
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Builds a GitHub "New issue" URL pre-filled with what Virtaal can
tell about itself - version, OS, install method - using GitHub's own
issue-forms query-string prefill (each field keyed by its id in
.github/ISSUE_TEMPLATE/bug_report.yml)."""

import platform as _platform_module
from urllib.parse import urlencode

from virtaal import __version__
from virtaal.common.platform import platform as _platform

REPO_URL = "https://github.com/translate/virtaal"

# GitHub's "os" dropdown only prefills on an exact option-text match.
_OS_LABELS = (
    ('is_windows', 'Windows'),
    ('is_mac', 'macOS'),
    ('is_linux', 'Linux'),
)


def _os_label(plat):
    for attr, label in _OS_LABELS:
        if getattr(plat, attr):
            return label
    return None


def build_bug_report_url(extra_fields=None, plat=None):
    """The URL for a pre-filled bug_report.yml issue.

        @type  extra_fields: dict
        @param extra_fields: Extra `field-id: value` pairs to prefill
            (e.g. `{'logs': traceback_text}`) - applied last, so these
            override anything built in here.
        @type  plat: virtaal.common.platform.Platform
        @param plat: Defaults to the real running platform - only
            passed explicitly by tests."""
    plat = plat if plat is not None else _platform

    fields = {'template': 'bug_report.yml', 'version': __version__.version_string()}

    os_label = _os_label(plat)
    if os_label:
        fields['os'] = os_label

    install_method = plat.install_method()
    if install_method:
        fields['install-method'] = install_method

    fields['os-version'] = _platform_module.platform()

    if extra_fields:
        fields.update(extra_fields)

    return "%s/issues/new?%s" % (REPO_URL, urlencode(fields))
