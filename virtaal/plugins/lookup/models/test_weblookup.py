#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gtk

from virtaal.plugins.lookup.models import weblookup
from virtaal.plugins.lookup.models.weblookup import (
    LookupModel,
    WebLookupAddDialog,
    WebLookupConfigDialog,
)
from virtaal.views import baseview


@pytest.fixture(autouse=True)
def _fresh_builder_cache(monkeypatch):
    monkeypatch.setattr(baseview, '_builders', {})


def test_treeview_scrolled_window_is_not_focusable():
    # The .ui file marks it focusable, which swallows Tab/Down meant
    # for the treeview inside it (confirmed live: Right-arrow/Down got
    # stuck, same issue as prefsview.py's plugin/placeables lists).
    dialog = WebLookupConfigDialog(parent=None)

    assert not dialog.tvw_urls.get_parent().get_can_focus()


def test_reopening_the_dialog_does_not_duplicate_columns():
    WebLookupConfigDialog(parent=None)
    dialog = WebLookupConfigDialog(parent=None)

    assert len(dialog.tvw_urls.get_columns()) == 4


def test_reopening_the_dialog_does_not_duplicate_button_handlers():
    calls = []

    class _FakeAddDialog:
        def run(self):
            calls.append('add')
            return None

    first = WebLookupConfigDialog(parent=None)
    first.add_dialog = _FakeAddDialog()
    second = WebLookupConfigDialog(parent=None)
    second.add_dialog = _FakeAddDialog()

    second.btn_url_add.clicked()

    assert len(calls) == 1


def test_every_instance_shares_the_same_url_list():
    first = WebLookupConfigDialog(parent=None)
    second = WebLookupConfigDialog(parent=None)

    second.urldata = [{'display_name': 'Example', 'url': 'http://example.com', 'quoted': False}]

    assert first.urldata == second.urldata


def test_run_restores_the_parents_focus_on_close(monkeypatch):
    monkeypatch.setattr(weblookup.GLib, 'idle_add', lambda func, *args: func(*args))
    dialog = WebLookupConfigDialog(parent=None)
    parent = Gtk.Window()
    calls = []
    monkeypatch.setattr(dialog.dialog, 'run', lambda: Gtk.ResponseType.CLOSE)
    monkeypatch.setattr(parent, 'present', lambda: calls.append('parent'))

    dialog.run(parent=parent)

    assert calls == ['parent']


def test_add_dialog_run_restores_the_parents_focus_on_close(monkeypatch):
    monkeypatch.setattr(weblookup.GLib, 'idle_add', lambda func, *args: func(*args))
    parent = Gtk.Window()
    dialog = WebLookupAddDialog(parent=parent)
    calls = []
    monkeypatch.setattr(dialog.dialog, 'run', lambda: Gtk.ResponseType.CANCEL)
    monkeypatch.setattr(parent, 'present', lambda: calls.append('parent'))

    dialog.run()

    assert calls == ['parent']


def test_add_dialog_derives_an_id_from_the_typed_name(monkeypatch):
    # Never asks the user for one directly.
    monkeypatch.setattr(weblookup.GLib, 'idle_add', lambda func, *args: func(*args))
    dialog = WebLookupAddDialog(parent=None)

    def _type_and_confirm():
        # run() resets the entries first - simulate the user typing
        # during the (here, mocked) modal call itself.
        dialog.ent_url_name.set_text('My Site')
        dialog.ent_url.set_text('http://example.com/?q=%(query)s')
        return Gtk.ResponseType.OK
    monkeypatch.setattr(dialog.dialog, 'run', _type_and_confirm)

    url = dialog.run()

    assert url['id'] == 'my_site'


# Disabling a web look-up

def _model(monkeypatch, tmp_path):
    monkeypatch.setattr(weblookup.pan_app, 'get_config_dir', lambda: str(tmp_path))
    return LookupModel('weblookup', controller=None)


def test_disabled_defaults_are_shipped_disabled(monkeypatch, tmp_path):
    # Bing/Yahoo are shipped as real entries, not left out entirely,
    # but disabled by default - redundant with Google for the
    # search-engine case.
    model = _model(monkeypatch, tmp_path)

    disabled_names = {u['display_name'] for u in model.URLDATA if not u['enabled']}

    assert disabled_names == {'Bing', 'Yahoo'}


def test_create_menu_items_skips_a_disabled_lookup(monkeypatch, tmp_path):
    model = _model(monkeypatch, tmp_path)
    model.URLDATA = [
        {'display_name': 'On', 'url': 'http://example.com/?q=%(query)s', 'quoted': False, 'enabled': True},
        {'display_name': 'Off', 'url': 'http://example.org/?q=%(query)s', 'quoted': False, 'enabled': False},
    ]

    items = model.create_menu_items('word', 'source', 'en', 'en', None)

    assert [i.get_label() for i in items] == ['On']


def test_create_menu_items_treats_a_missing_enabled_key_as_enabled(monkeypatch, tmp_path):
    # A user's own custom entry, saved before this key existed.
    model = _model(monkeypatch, tmp_path)
    model.URLDATA = [{'display_name': 'Custom', 'url': 'http://example.com/?q=%(query)s', 'quoted': False}]

    items = model.create_menu_items('word', 'source', 'en', 'en', None)

    assert [i.get_label() for i in items] == ['Custom']


def test_load_urldata_defaults_a_saved_entry_without_enabled_to_enabled(monkeypatch, tmp_path):
    monkeypatch.setattr(weblookup.pan_app, 'get_config_dir', lambda: str(tmp_path))
    (tmp_path / 'weblookup.ini').write_text(
        '[Old Custom]\ndisplay_name = Old Custom\nurl = http://example.com/?q=%(query)s\nquoted = False\n')

    model = LookupModel('weblookup', controller=None)

    saved = next(u for u in model.URLDATA if u['display_name'] == 'Old Custom')
    assert saved['enabled'] is True


def test_load_urldata_adds_new_defaults_missing_from_a_saved_config(monkeypatch, tmp_path):
    # A config saved before Bing/Yahoo existed only has the original
    # three entries - they shouldn't vanish just because a user
    # already had a weblookup.ini.
    monkeypatch.setattr(weblookup.pan_app, 'get_config_dir', lambda: str(tmp_path))
    (tmp_path / 'weblookup.ini').write_text(
        '[Google]\ndisplay_name = Google\nurl = http://www.google.com/search?q=%(query)s\nquoted = True\nenabled = True\n')

    model = LookupModel('weblookup', controller=None)

    names = {u['display_name']: u['enabled'] for u in model.URLDATA}
    assert names['Google'] is True
    assert names['Bing'] is False
    assert names['Yahoo'] is False


def test_enabled_toggle_updates_the_underlying_url_dict():
    dialog = WebLookupConfigDialog(parent=None)
    url = {'display_name': 'Example', 'url': 'http://example.com', 'quoted': False, 'enabled': True}
    dialog.urldata = [url]

    dialog._on_enabled_toggled(None, '0')

    assert dialog.lst_urls[0][dialog.COL_ENABLED] is False
    assert dialog.urldata[0]['enabled'] is False


def test_quote_toggle_updates_the_underlying_url_dict():
    # Pre-existing gap, same root cause as the enabled toggle above:
    # the CellRendererToggle had no 'toggled' handler at all, so a
    # click showed the checkbox flip but never actually saved it.
    dialog = WebLookupConfigDialog(parent=None)
    url = {'display_name': 'Example', 'url': 'http://example.com', 'quoted': False, 'enabled': True}
    dialog.urldata = [url]

    dialog._on_quote_toggled(None, '0')

    assert dialog.lst_urls[0][dialog.COL_QUOTE] is True
    assert dialog.urldata[0]['quoted'] is True


def test_save_urldata_keys_by_id_not_the_translatable_display_name(monkeypatch, tmp_path):
    # display_name is translated for the menu - it must not also be
    # the saved config's own section name, or a translated UI language
    # renders the built-in look-ups unrecognisable on the next load.
    monkeypatch.setattr(weblookup.pan_app, 'get_config_dir', lambda: str(tmp_path))
    model = _model(monkeypatch, tmp_path)
    # Simulates a translated UI - display_name in Arabic, as if a
    # translator had rendered "Google" into Arabic script.
    model.URLDATA = [dict(u) for u in type(model).URLDATA]
    for u in model.URLDATA:
        if u['id'] == 'google':
            u['display_name'] = 'ﺝﻮﺠﻟ'

    model.destroy()

    saved = weblookup.pan_app.load_config(model.urldata_file)
    assert 'google' in saved
    assert saved['google']['display_name'] == 'ﺝﻮﺠﻟ'


def test_load_urldata_resolves_a_legacy_saves_id_by_display_name(monkeypatch, tmp_path):
    # A save from before 'id' existed only has display_name - matching
    # it against the current defaults' own display_name recovers the
    # right id instead of treating it as a separate custom entry.
    monkeypatch.setattr(weblookup.pan_app, 'get_config_dir', lambda: str(tmp_path))
    (tmp_path / 'weblookup.ini').write_text(
        '[Google]\ndisplay_name = Google\nurl = http://www.google.com/search?q=%(query)s\nquoted = True\nenabled = True\n')

    model = LookupModel('weblookup', controller=None)

    google = next(u for u in model.URLDATA if u['display_name'] == 'Google')
    assert google['id'] == 'google'


def test_configure_saves_immediately_rather_than_waiting_for_destroy(monkeypatch, tmp_path):
    monkeypatch.setattr(weblookup.pan_app, 'get_config_dir', lambda: str(tmp_path))
    model = LookupModel('weblookup', controller=None)

    class _FakeConfigureDialog:
        def __init__(self, parent):
            self.urldata = None

        def run(self):
            # Simulates the user editing the list before closing the
            # dialog - a real dialog's urldata only reflects this once
            # run() returns, not before.
            self.urldata = [
                {'display_name': 'Only', 'url': 'http://example.com/?q=%(query)s', 'quoted': False, 'enabled': True},
            ]

    monkeypatch.setattr(weblookup, 'WebLookupConfigDialog', lambda parent: _FakeConfigureDialog(parent))
    parent = type('_FakeParent', (), {'get_toplevel': lambda self: None})()

    model.configure(parent)

    reloaded = weblookup.pan_app.load_config(model.urldata_file)
    assert 'Only' in reloaded
