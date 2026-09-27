#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import GObject

from virtaal.plugins.tm.models.amagama import TMModel


def _model():
    model = TMModel.__new__(TMModel)
    GObject.GObject.__init__(model)
    return model


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


# __init__(): only overrides push_store/upload_store/__init__ itself -
# calls BaseTMModel.__init__() directly (not remotetm.TMModel's, which
# does more than amagama wants) and builds a real TMClient from the
# configured url.

def test_init_loads_config_and_builds_a_tmclient(monkeypatch):
    monkeypatch.setattr(TMModel, 'load_config', lambda self: setattr(self, 'config', {'url': 'https://example.com/api/v1/'}))

    model = TMModel('amagama', _fake_controller())

    assert model.internal_name == 'amagama'
    assert model.tmclient.base_url == 'https://example.com/api/v1/'
    assert model.tmclient.user_agent.startswith('Virtaal')


def test_amagama_inherits_remotetms_query_logic():
    # Amagama only overrides __init__/push_store/upload_store - the
    # actual query()/_handle_matches() logic is remotetm's own.
    model = _model()
    model.source_lang = 'en'
    model.target_lang = 'af'
    model.checker = None
    model.cache = {}
    calls = []
    model.tmclient = SimpleNamespace(translate_unit=lambda *a: calls.append(a))

    model.query(None, SimpleNamespace(source='hello'))

    assert calls[0][:3] == ('hello', 'en', 'af')


def test_push_store_is_a_no_op():
    model = _model()

    model.push_store(SimpleNamespace())  # must not raise


def test_upload_store_is_a_no_op():
    model = _model()

    model.upload_store(SimpleNamespace())  # must not raise
