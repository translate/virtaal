#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Translates units through the Apertium plugin and the live service,
with Virtaal's own language codes, and checks every language code the
service lists can be reached from a Virtaal code (#4661, #4664).
Skipped unless VIRTAAL_LIVE_SERVICES=1."""

import os
from types import SimpleNamespace

import pycountry
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


@pytest.fixture(scope='module')
def model(tmp_path_factory):
    from unittest import mock
    config_dir = str(tmp_path_factory.mktemp('config'))
    with mock.patch('virtaal.common.pan_app.get_config_dir', lambda: config_dir):
        from virtaal.plugins.tm.models.apertium import TMModel
        model = TMModel('apertium', _fake_controller())
        _run_until(lambda: model.language_pairs, 30)
    assert model.language_pairs, 'no language pairs from %s within 30 s' % model.url_getpairs
    return model


@pytest.mark.parametrize('source, target, expected', [
    ('en', 'ca', 'La casa és gran.'),
    ('en', 'ca@valencia', None),
])
def test_translates_with_virtaal_codes(model, source, target, expected):
    model.source_lang, model.target_lang = source, target
    model.cache = {}
    found = []
    handler = model.connect('match-found', lambda model, query, matches: found.append(matches))
    try:
        model.query(None, SimpleNamespace(source='The house is big.'))
        _run_until(lambda: found, 30)
    finally:
        model.disconnect(handler)

    assert found, 'no Apertium translation for %s -> %s within 30 s' % (source, target)
    if expected:
        assert found[0][0]['target'] == expected
    else:
        assert found[0][0]['target'].strip()


def _virtaal_code(apy_code):
    """The code a Virtaal user would use for an APY code: two-letter
    where one exists, a region as _XX, anything else as @variant."""
    from virtaal.plugins.tm.models.apertium import APY_LANGUAGES
    for virtaal, apy in APY_LANGUAGES.items():
        if apy == apy_code:
            return virtaal
    base, _, variant = apy_code.partition('_')
    language = pycountry.languages.get(alpha_3=base)
    code = getattr(language, 'alpha_2', None) or base
    if not variant:
        return code
    if len(variant) == 2 and variant.isupper():
        return code + '_' + variant
    return code + '@' + variant


def test_every_listed_language_is_reachable(model):
    from virtaal.plugins.tm.models.apertium import apy_codes
    listed = sorted({code for pair in model.language_pairs for code in pair})
    unreachable = ['%s (from %s: %s)' % (code, _virtaal_code(code), apy_codes(_virtaal_code(code)))
                   for code in listed if code not in apy_codes(_virtaal_code(code))]
    assert not unreachable, 'APY codes no Virtaal code reaches:\n' + '\n'.join(unreachable)


def test_every_override_is_still_listed(model):
    from virtaal.plugins.tm.models.apertium import APY_LANGUAGES
    listed = {code for pair in model.language_pairs for code in pair}
    gone = {virtaal: apy for virtaal, apy in APY_LANGUAGES.items() if apy not in listed}
    assert not gone, 'APY_LANGUAGES entries APY no longer lists: %s' % gone
