#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Translates a unit through the Apertium plugin and the live service,
with Virtaal's own language codes (#4661). Skipped unless
VIRTAAL_LIVE_SERVICES=1."""

import os
from types import SimpleNamespace

import pytest
from gi.repository import GLib

from virtaal.plugins.tm.models.test_amagama import _fake_controller

pytestmark = pytest.mark.skipif(
    os.environ.get('VIRTAAL_LIVE_SERVICES') != '1',
    reason="set VIRTAAL_LIVE_SERVICES=1 to query the live Apertium service")


def _run_until(condition, seconds):
    loop = GLib.MainLoop()

    def poll():
        if condition():
            loop.quit()
            return False
        return True
    GLib.timeout_add(200, poll)
    GLib.timeout_add_seconds(seconds, loop.quit)
    loop.run()


def test_english_to_catalan(monkeypatch, tmp_path):
    monkeypatch.setattr('virtaal.common.pan_app.get_config_dir', lambda: str(tmp_path))
    from virtaal.plugins.tm.models.apertium import TMModel

    model = TMModel('apertium', _fake_controller())
    _run_until(lambda: model.language_pairs, 30)
    assert model.language_pairs, 'no language pairs from %s within 30 s' % model.url_getpairs

    model.source_lang, model.target_lang = 'en', 'ca'
    model.cache = {}
    found = []
    model.connect('match-found', lambda model, query, matches: found.append(matches))
    model.query(None, SimpleNamespace(source='The house is big.'))
    _run_until(lambda: found, 30)

    assert found, 'no Apertium translation for en -> ca within 30 s (%d pairs listed)' % len(model.language_pairs)
    assert found[0][0]['target'] == 'La casa és gran.'
