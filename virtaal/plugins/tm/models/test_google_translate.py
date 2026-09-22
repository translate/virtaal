#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from virtaal.plugins.tm.models import google_translate
from virtaal.plugins.tm.models.google_translate import TMModel


# __init__(): with an API key configured, the languages-list request
# must actually build from languages_url (url_getlanguages doesn't
# exist - a plain AttributeError on every real launch with a key set).

class _FakeHTTPClient:
    def __init__(self):
        self.added = []

    def add(self, request):
        self.added.append(request)


def _fake_controller():
    connectable = lambda: SimpleNamespace(connect=lambda signal, handler, *a: 1)
    lang_controller = connectable()
    lang_controller.source_lang = SimpleNamespace(code='en')
    lang_controller.target_lang = SimpleNamespace(code='af')
    checks_controller = connectable()
    checks_controller.code = 'standard'
    main_controller = SimpleNamespace(lang_controller=lang_controller, checks_controller=checks_controller)
    controller = connectable()
    controller.main_controller = main_controller
    return controller


def test_init_builds_the_languages_request_from_languages_url(monkeypatch):
    monkeypatch.setattr(google_translate, 'HTTPClient', _FakeHTTPClient)
    monkeypatch.setattr(TMModel, 'load_config', lambda self: setattr(self, 'config', {'api_key': 'test-key'}))

    model = TMModel('google_translate', _fake_controller())

    assert len(model.client.added) == 1
    assert model.client.added[0].url == model.languages_url % {'key': 'test-key'}
