#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""A real lookup on the live amaGama server, through Virtaal's own client.

Skipped unless VIRTAAL_LIVE_SERVICES=1, so pull request CI neither depends
on the public server nor loads it. Runs weekly (live-services.yml) and
before a release.
"""

import os
from types import SimpleNamespace

import pytest
from gi.repository import GLib

from virtaal.plugins.tm.models.amagama import TMModel
from virtaal.plugins.tm.models.test_amagama import _fake_controller

pytestmark = pytest.mark.skipif(
    os.environ.get('VIRTAAL_LIVE_SERVICES') != '1',
    reason="set VIRTAAL_LIVE_SERVICES=1 to query the live amaGama server")


def test_lookup_on_the_live_server(monkeypatch, tmp_path):
    monkeypatch.setattr('virtaal.common.pan_app.get_config_dir', lambda: str(tmp_path))
    model = TMModel('amagama', _fake_controller())
    assert model.tmclient.base_url == TMModel.default_config['url']
    model.source_lang = 'en'
    model.target_lang = 'af'
    model.checker = None
    model.cache = {}

    found = []
    loop = GLib.MainLoop()

    def match_found(model, query, matches):
        found.append(matches)
        loop.quit()

    model.connect('match-found', match_found)
    GLib.timeout_add_seconds(20, loop.quit)
    model.query(None, SimpleNamespace(source='File'))
    loop.run()

    assert found, "no reply from %s within 20 s" % model.tmclient.base_url
    matches = found[0]
    assert all({'source', 'target', 'quality', 'tmsource'} <= set(m) for m in matches)
    assert 'Lêer' in [m['target'] for m in matches]
