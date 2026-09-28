#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os
import tempfile
from types import SimpleNamespace

import pytest
from gi.repository import GLib, Gtk

from virtaal.common import GObjectWrapper, pan_app
from virtaal.common.platform import platform
from virtaal.controllers.maincontroller import MainController


def test_open_file_gives_up_instead_of_hanging_forever(monkeypatch):
    # placeables_controller never gets set here (unlike the real app's
    # own startup sequence) - a re-entrant open_file() call arriving
    # during this wait used to recurse through it forever.
    controller = MainController.__new__(MainController)
    controller._placeables_controller = None
    controller._opening_file = False
    controller.view = SimpleNamespace(open_file=lambda: 'welcome-screen')
    iterations = []
    monkeypatch.setattr(Gtk, 'main_iteration', lambda: iterations.append(1))

    result = controller.open_file(None)  # must not hang

    assert len(iterations) == 1000
    assert result == 'welcome-screen'


def test_open_file_ignores_a_reentrant_call():
    # A macOS "open file" event's callback re-entering open_file()
    # while an outer call is still running (e.g. from inside the wait
    # loop above) used to recurse without bound - the actual thing
    # that made the wait loop's own bound not enough on its own.
    controller = MainController.__new__(MainController)
    controller._opening_file = True

    assert controller.open_file('somefile.po') is None


def test_open_file_shows_a_translated_error_message_on_failure():
    # The wait loop's own `for _ in range(1000)` used to shadow the
    # gettext `_` builtin for the rest of this method, so the error
    # message below raised TypeError instead of ever reaching the
    # dialog.
    def raise_missing(*args, **kwargs):
        raise OSError('The file does not exist.')

    controller = MainController.__new__(MainController)
    controller._opening_file = False
    controller._placeables_controller = object()
    controller._store_controller = SimpleNamespace(is_modified=lambda: False, open_file=raise_missing, store=None)
    errors = []
    controller.view = SimpleNamespace(show_error_dialog=lambda message, parent=None: errors.append(message))

    result = controller.open_file('missing.po')

    assert result is False
    assert errors == ['missing.po:\nCould not open file.\n\nThe file does not exist.\n\nTry opening a different file.']


def test_quit_closes_a_still_open_dialog_and_retries_instead_of_hanging(monkeypatch):
    # macOS's global Cmd+Q accelerator can reach quit() while a
    # Gtk.Dialog.run() (Preferences, Properties, ...) is still blocking
    # its own separate main loop - proceeding to tear the app down
    # would leave that loop stuck forever, with no window left to give
    # it the response it's waiting for.
    main_window = Gtk.Window()
    dialog = Gtk.Dialog()
    dialog.show()

    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(main_window=main_window)
    monkeypatch.setattr(Gtk.Window, 'list_toplevels', lambda: [main_window, dialog])
    responses = []
    monkeypatch.setattr(dialog, 'response', responses.append)
    idle_calls = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: idle_calls.append((func, args)))

    result = controller.quit()

    assert responses == [Gtk.ResponseType.CANCEL]
    assert idle_calls == [(controller.quit, (False,))]
    assert result is False


def test_quit_closes_every_open_dialog_not_just_the_first(monkeypatch):
    # A dialog nested inside another one (e.g. a plugin's own
    # sub-dialog opened from within Preferences) leaves the outer one
    # still blocked too if only the inner one gets a response.
    main_window = Gtk.Window()
    outer_dialog = Gtk.Dialog()
    inner_dialog = Gtk.Dialog()
    outer_dialog.show()
    inner_dialog.show()

    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(main_window=main_window)
    monkeypatch.setattr(Gtk.Window, 'list_toplevels', lambda: [main_window, outer_dialog, inner_dialog])
    responses = []
    monkeypatch.setattr(outer_dialog, 'response', lambda r: responses.append((outer_dialog, r)))
    monkeypatch.setattr(inner_dialog, 'response', lambda r: responses.append((inner_dialog, r)))
    monkeypatch.setattr(GLib, 'idle_add', lambda func, *args: None)

    controller.quit()

    assert responses == [
        (outer_dialog, Gtk.ResponseType.CANCEL),
        (inner_dialog, Gtk.ResponseType.CANCEL),
    ]


def test_open_file_with_no_filename_actually_opens_the_chosen_one(monkeypatch):
    # view.open_file() (the welcome screen's "Open" link, or an empty
    # File>Open) shows a chooser and calls back into open_file() with
    # the chosen filename - the guard, still set from this outer
    # filename=None call, used to silently swallow that real one too.
    controller = MainController.__new__(MainController)
    controller._placeables_controller = object()
    controller._opening_file = False
    opened = []
    controller._store_controller = SimpleNamespace(
        is_modified=lambda: False,
        open_file=lambda filename, uri, forget_dir=False: opened.append(filename),
        store=None,
    )
    controller._mode_controller = SimpleNamespace(refresh_mode=lambda: None)
    controller.view = SimpleNamespace(open_file=lambda: controller.open_file('chosen.po'))

    controller.open_file(None)

    assert opened == ['chosen.po']


def _controller_for_export(bundle_filename, raises=None):
    calls = {'export': [], 'error': None}

    def binary_export(filename):
        calls['export'].append(filename)
        if raises:
            raise raises

    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(
        show_save_dialog=lambda current_filename, title: current_filename,
        show_error_dialog=lambda message, parent=None: calls.__setitem__('error', message),
    )
    controller._store_controller = SimpleNamespace(
        get_bundle_filename=lambda: bundle_filename,
        binary_export=binary_export,
    )
    controller.calls = calls
    return controller


def test_binary_export_rejects_a_non_po_filename():
    controller = _controller_for_export('document.odt')

    result = controller.binary_export()

    assert result is False
    assert controller.calls['export'] == []
    assert controller.calls['error'] is not None


def test_binary_export_derives_the_mo_filename_from_a_po_file():
    controller = _controller_for_export('translations/af.po')

    result = controller.binary_export()

    assert result is True
    assert controller.calls['export'] == ['translations/af.mo']


def test_binary_export_falls_back_to_a_generic_name_for_a_compressed_po():
    # .po.bz2/.po.gz pass the initial extension check but don't end in
    # plain ".po", so the specific base name is lost - a real, current
    # limitation worth pinning down, not obviously intentional.
    controller = _controller_for_export('translations/af.po.gz')

    result = controller.binary_export()

    assert result is True
    assert controller.calls['export'] == ['messages.mo']


def test_binary_export_returns_false_if_the_save_dialog_is_cancelled():
    controller = _controller_for_export('translations/af.po')
    controller.view.show_save_dialog = lambda current_filename, title: ''

    result = controller.binary_export()

    assert result is False
    assert controller.calls['export'] == []


def test_binary_export_shows_an_error_and_returns_false_on_oserror():
    controller = _controller_for_export('translations/af.po', raises=OSError('disk full'))

    result = controller.binary_export()

    assert result is False
    assert controller.calls['error'] is not None


def _controller_for_save(save_raises=None):
    calls = {'saved': []}

    def save_file(filename):
        calls['saved'].append(filename)
        if save_raises:
            raise save_raises

    controller = MainController.__new__(MainController)
    controller._force_saveas = False
    controller._store_controller = SimpleNamespace(save_file=save_file)
    controller.calls = calls
    return controller


def test_save_file_with_a_filename_skips_the_saveas_dialog():
    controller = _controller_for_save()

    result = controller.save_file(filename='explicit.po')

    assert result is True
    assert controller.calls['saved'] == ['explicit.po']


def test_save_file_prompts_for_a_filename_when_forced_to_save_as():
    controller = _controller_for_save()
    controller._store_controller.get_bundle_filename = lambda: None
    controller.get_store_filename = lambda: 'current.po'
    controller.view = SimpleNamespace(show_save_dialog=lambda current_filename, title: 'chosen.po')

    result = controller.save_file(force_saveas=True)

    assert result is True
    assert controller.calls['saved'] == ['chosen.po']


def test_save_file_returns_false_if_the_saveas_dialog_is_cancelled():
    controller = _controller_for_save()
    controller._store_controller.get_bundle_filename = lambda: None
    controller.get_store_filename = lambda: 'current.po'
    controller.view = SimpleNamespace(show_save_dialog=lambda current_filename, title: '')

    result = controller.save_file(force_saveas=True)

    assert result is False
    assert controller.calls['saved'] == []


def test_save_file_clears_force_saveas_after_a_successful_save():
    controller = _controller_for_save()
    controller._force_saveas = True

    controller.save_file(filename='explicit.po')

    assert controller.get_force_saveas() is False


@pytest.mark.skipif(platform.is_windows, reason="os.chmod doesn't model POSIX write permission on Windows")
def test_save_file_rejects_a_readonly_target_before_ever_calling_save(tmp_path):
    # A Save As target can be read-only too (the original file, confirmed
    # to replace) - must fail here, before any header-info prompts (#517).
    controller = _controller_for_save()
    real_file = tmp_path / "readonly.po"
    real_file.write_text("")
    os.chmod(real_file, 0o444)
    errors = []
    controller.view = SimpleNamespace(show_error_dialog=lambda message, parent=None: errors.append(message))

    try:
        result = controller.save_file(filename=str(real_file))
    finally:
        os.chmod(real_file, 0o644)  # allow tmp_path's own cleanup to remove it

    assert result is False
    assert controller.calls['saved'] == []
    assert len(errors) == 1


def test_do_save_file_shows_an_error_dialog_on_oserror():
    controller = _controller_for_save(save_raises=OSError('disk full'))
    errors = []
    controller.view = SimpleNamespace(show_error_dialog=lambda message, parent=None: errors.append(message))

    result = controller.save_file(filename='explicit.po')

    assert result is False
    assert len(errors) == 1


def test_do_save_file_shows_an_error_dialog_on_a_generic_exception():
    controller = _controller_for_save(save_raises=ValueError('unexpected'))
    errors = []
    controller.view = SimpleNamespace(show_error_dialog=lambda message, parent=None: errors.append(message))

    result = controller.save_file(filename='explicit.po')

    assert result is False
    assert len(errors) == 1


def test_close_file_closes_directly_when_not_modified():
    calls = []
    controller = MainController.__new__(MainController)
    controller._store_controller = SimpleNamespace(
        is_modified=lambda: False,
        close_file=lambda: calls.append('closed'),
    )

    controller.close_file()

    assert calls == ['closed']


def test_close_file_does_not_close_when_the_user_cancels_the_save_prompt():
    calls = []
    controller = MainController.__new__(MainController)
    controller._store_controller = SimpleNamespace(
        is_modified=lambda: True,
        close_file=lambda: calls.append('closed'),
    )
    controller.view = SimpleNamespace(show_save_confirm_dialog=lambda: 'cancel')

    result = controller.close_file()

    assert result is False
    assert calls == []


def test_close_file_closes_after_discarding_changes():
    calls = []
    controller = MainController.__new__(MainController)
    controller._store_controller = SimpleNamespace(
        is_modified=lambda: True,
        close_file=lambda: calls.append('closed'),
    )
    controller.view = SimpleNamespace(show_save_confirm_dialog=lambda: 'discard')

    controller.close_file()

    assert calls == ['closed']


def test_show_template_update_notice_delegates_to_the_view():
    shown = []
    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(show_template_update_notice=lambda title, msg: shown.append((title, msg)))

    controller.show_template_update_notice('File Updated', 'Before:\n\tTranslated: 1')

    assert shown == [('File Updated', 'Before:\n\tTranslated: 1')]


# open_file()'s remaining branches: save-confirm, file:// stripping, reload-prompt #

def _controller_for_open_file(is_modified=False, store=None):
    controller = MainController.__new__(MainController)
    controller._opening_file = False
    controller._placeables_controller = object()
    controller._store_controller = SimpleNamespace(
        is_modified=lambda: is_modified,
        store=store,
        open_file=lambda filename, uri, forget_dir=False: None,
    )
    controller._mode_controller = SimpleNamespace(refresh_mode=lambda: None)
    controller.view = SimpleNamespace()
    return controller


def test_open_file_returns_false_when_the_user_cancels_the_save_prompt():
    controller = _controller_for_open_file(is_modified=True)
    controller.view.show_save_confirm_dialog = lambda: 'cancel'
    controller._store_controller.open_file = lambda *a, **k: pytest.fail('must not open without resolving the save prompt')

    assert controller.open_file('other.po') is False


def test_open_file_saves_first_when_the_user_confirms_the_save_prompt():
    calls = []
    controller = _controller_for_open_file(is_modified=True)
    controller.view.show_save_confirm_dialog = lambda: 'save'
    controller.save_file = lambda: calls.append('saved') or True
    controller._store_controller.open_file = lambda filename, uri, forget_dir=False: calls.append(('opened', filename))

    result = controller.open_file('other.po')

    assert result is True
    assert calls == ['saved', ('opened', 'other.po')]


def test_open_file_returns_false_when_the_save_itself_fails():
    controller = _controller_for_open_file(is_modified=True)
    controller.view.show_save_confirm_dialog = lambda: 'save'
    controller.save_file = lambda: False
    controller._store_controller.open_file = lambda *a, **k: pytest.fail('must not open after a failed save')

    assert controller.open_file('other.po') is False


def test_open_file_strips_a_windows_file_uri(monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', True)
    opened = []
    controller = _controller_for_open_file()
    controller._store_controller.open_file = lambda filename, uri, forget_dir=False: opened.append(filename)

    controller.open_file('file:///C:/translations/af.po')

    assert opened == ['C:/translations/af.po']


def test_open_file_strips_a_posix_file_uri(monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', False)
    opened = []
    controller = _controller_for_open_file()
    controller._store_controller.open_file = lambda filename, uri, forget_dir=False: opened.append(filename)

    controller.open_file('file:///home/user/af.po')

    assert opened == ['/home/user/af.po']


def test_open_file_asks_to_reload_the_currently_open_file():
    controller = _controller_for_open_file(store=SimpleNamespace(get_filename=lambda: 'current.po'))
    controller.view.show_prompt_dialog = lambda **kwargs: False

    assert controller.open_file('current.po') is False


def test_open_file_reloads_the_currently_open_file_on_confirmation():
    opened = []
    controller = _controller_for_open_file(store=SimpleNamespace(get_filename=lambda: 'current.po'))
    controller.view.show_prompt_dialog = lambda **kwargs: True
    controller._store_controller.open_file = lambda filename, uri, forget_dir=False: opened.append(filename)

    result = controller.open_file('current.po')

    assert result is True
    assert opened == ['current.po']


# open_tutorial() #

def test_open_tutorial_opens_a_localized_copy_and_cleans_up_afterwards(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    tutorial_path = os.path.join(tmpdir, 'tutorial.po')
    with open(tutorial_path, 'w') as f:
        f.write('')
    monkeypatch.setattr('virtaal.support.tutorial.create_localized_tutorial', lambda: tutorial_path)
    opened = []
    controller = MainController.__new__(MainController)
    controller.open_file = lambda filename, forget_dir=False: opened.append((filename, forget_dir))

    controller.open_tutorial()

    assert opened == [(tutorial_path, True)]
    assert not os.path.isdir(tmpdir)


# update_file() #

def _controller_for_update_file(is_modified=False, store=None):
    controller = MainController.__new__(MainController)
    controller._store_controller = SimpleNamespace(
        is_modified=lambda: is_modified,
        store=store,
        update_file=lambda filename, uri: None,
    )
    controller._mode_controller = SimpleNamespace(refresh_mode=lambda: None)
    controller.view = SimpleNamespace()
    return controller


def test_update_file_succeeds_and_refreshes_the_mode():
    calls = []
    controller = _controller_for_update_file()
    controller._store_controller.update_file = lambda filename, uri: calls.append((filename, uri))
    controller._mode_controller.refresh_mode = lambda: calls.append('refreshed')

    result = controller.update_file('template.pot', uri='http://x')

    assert result is True
    assert calls == [('template.pot', 'http://x'), 'refreshed']


def test_update_file_returns_false_when_the_user_cancels_the_save_prompt():
    controller = _controller_for_update_file(is_modified=True)
    controller.view.show_save_confirm_dialog = lambda: 'cancel'
    controller._store_controller.update_file = lambda *a: pytest.fail('must not update without resolving the save prompt')

    assert controller.update_file('template.pot') is False


def test_update_file_saves_first_when_the_user_confirms_the_save_prompt():
    calls = []
    controller = _controller_for_update_file(is_modified=True)
    controller.view.show_save_confirm_dialog = lambda: 'save'
    controller.save_file = lambda: calls.append('saved') or True
    controller._store_controller.update_file = lambda filename, uri: calls.append(('update', filename))

    result = controller.update_file('template.pot')

    assert result is True
    assert calls == ['saved', ('update', 'template.pot')]


def test_update_file_returns_false_when_the_save_itself_fails():
    controller = _controller_for_update_file(is_modified=True)
    controller.view.show_save_confirm_dialog = lambda: 'save'
    controller.save_file = lambda: False
    controller._store_controller.update_file = lambda *a: pytest.fail('must not update after a failed save')

    assert controller.update_file('template.pot') is False


def test_update_file_asks_to_reload_when_the_template_is_the_currently_open_file():
    controller = _controller_for_update_file(store=SimpleNamespace(get_filename=lambda: 'same.po'))
    controller.view.show_prompt_dialog = lambda **kwargs: False

    assert controller.update_file('same.po') is False


def test_update_file_shows_an_error_on_failure():
    controller = _controller_for_update_file()
    errors = []
    controller.view.show_error_dialog = lambda message, parent=None: errors.append(message)

    def raise_missing(filename, uri):
        raise OSError('nope')
    controller._store_controller.update_file = raise_missing

    result = controller.update_file('missing.pot')

    assert result is False
    assert len(errors) == 1


# revert_file() #

def test_revert_file_does_nothing_when_the_user_declines_to_confirm():
    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(show_prompt_dialog=lambda **kwargs: False)
    controller._store_controller = SimpleNamespace(revert_file=lambda: pytest.fail('must not revert without confirmation'))

    controller.revert_file()


def test_revert_file_reverts_and_refreshes_the_mode_on_confirmation():
    calls = []
    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(show_prompt_dialog=lambda **kwargs: True)
    controller._store_controller = SimpleNamespace(revert_file=lambda: calls.append('reverted'))
    controller._mode_controller = SimpleNamespace(refresh_mode=lambda: calls.append('refreshed'))

    controller.revert_file()

    assert calls == ['reverted', 'refreshed']


def test_revert_file_shows_an_error_on_failure():
    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(show_prompt_dialog=lambda **kwargs: True)
    errors = []
    controller.view.show_error_dialog = lambda message, parent=None: errors.append(message)

    def raise_missing():
        raise OSError('gone')
    controller._store_controller = SimpleNamespace(revert_file=raise_missing)

    controller.revert_file(filename='was.po')

    assert len(errors) == 1


# close_file()'s remaining branch #

def test_close_file_does_not_close_when_the_save_itself_fails():
    calls = []
    controller = MainController.__new__(MainController)
    controller._store_controller = SimpleNamespace(
        is_modified=lambda: True,
        close_file=lambda: calls.append('closed'),
    )
    controller.view = SimpleNamespace(show_save_confirm_dialog=lambda: 'save')
    controller.save_file = lambda: False

    result = controller.close_file()

    assert result is False
    assert calls == []


# binary_export()'s remaining branches #

def test_binary_export_falls_back_to_the_store_filename_without_a_bundle_filename():
    controller = _controller_for_export(bundle_filename=None)
    controller.get_store_filename = lambda: 'fallback.po'

    result = controller.binary_export()

    assert result is True
    assert controller.calls['export'] == ['fallback.mo']


def test_binary_export_shows_an_error_and_returns_false_on_a_generic_exception():
    controller = _controller_for_export('translations/af.po', raises=ValueError('boom'))

    result = controller.binary_export()

    assert result is False
    assert controller.calls['error'] is not None


# get_translator_name()/email()/team() #

def test_get_translator_name_returns_the_configured_name(monkeypatch):
    monkeypatch.setattr(pan_app.settings, 'translator', {'name': 'Dwayne'})
    controller = MainController.__new__(MainController)

    assert controller.get_translator_name() == 'Dwayne'


def test_get_translator_name_prompts_when_not_configured(monkeypatch):
    monkeypatch.setattr(pan_app.settings, 'translator', {'name': ''})
    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(show_input_dialog=lambda title, message: 'entered')

    assert controller.get_translator_name() == 'entered'


def test_get_translator_email_returns_the_configured_email(monkeypatch):
    monkeypatch.setattr(pan_app.settings, 'translator', {'email': 'translator@example.com'})
    controller = MainController.__new__(MainController)

    assert controller.get_translator_email() == 'translator@example.com'


def test_get_translator_email_prompts_when_not_configured(monkeypatch):
    monkeypatch.setattr(pan_app.settings, 'translator', {'email': ''})
    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(show_input_dialog=lambda title, message: 'entered@example.com')

    assert controller.get_translator_email() == 'entered@example.com'


def test_get_translator_team_returns_the_configured_team(monkeypatch):
    monkeypatch.setattr(pan_app.settings, 'translator', {'team': 'af'})
    controller = MainController.__new__(MainController)

    assert controller.get_translator_team() == 'af'


def test_get_translator_team_prompts_when_not_configured(monkeypatch):
    monkeypatch.setattr(pan_app.settings, 'translator', {'team': ''})
    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(show_input_dialog=lambda title, message: 'Team Zed')

    assert controller.get_translator_team() == 'Team Zed'


# trivial delegators #

def test_select_unit_delegates_to_the_store_controller():
    calls = []
    controller = MainController.__new__(MainController)
    controller._store_controller = SimpleNamespace(select_unit=lambda unit, force: calls.append((unit, force)))

    controller.select_unit('a-unit', force=True)

    assert calls == [('a-unit', True)]


def test_show_input_delegates_to_the_view():
    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(show_input_dialog=lambda title, message: (title, message))

    assert controller.show_input('T', 'M') == ('T', 'M')


def test_show_prompt_delegates_to_the_view():
    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(show_prompt_dialog=lambda title, message, parent: (title, message, parent))

    assert controller.show_prompt('T', 'M', parent='P') == ('T', 'M', 'P')


def test_show_info_delegates_to_the_view():
    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(show_info_dialog=lambda title, message, parent: (title, message, parent))

    assert controller.show_info('T', 'M', parent='P') == ('T', 'M', 'P')


def test_run_shows_the_view():
    calls = []
    controller = MainController.__new__(MainController)
    controller.view = SimpleNamespace(show=lambda: calls.append('shown'))

    controller.run()

    assert calls == ['shown']


# load_plugins() / destroy() #

def test_load_plugins_delegates_when_a_plugin_controller_is_registered():
    controller = MainController.__new__(MainController)
    calls = []
    controller._plugin_controller = SimpleNamespace(load_plugins=lambda: calls.append('loaded'))

    controller.load_plugins()

    assert calls == ['loaded']


def test_load_plugins_does_nothing_without_a_plugin_controller():
    controller = MainController.__new__(MainController)
    controller._plugin_controller = None

    controller.load_plugins()  # must not raise


def test_destroy_delegates_to_the_store_controller():
    controller = MainController.__new__(MainController)
    calls = []
    controller._store_controller = SimpleNamespace(destroy=lambda: calls.append('destroyed'))

    controller.destroy()

    assert calls == ['destroyed']


# plugin_controller / welcomescreen_controller properties - the only two
# never exercised by any real controller's own construction #

def test_plugin_controller_property_emits_controller_registered():
    controller = MainController.__new__(MainController)
    GObjectWrapper.__init__(controller)
    registered = []
    controller.connect('controller-registered', lambda _c, value: registered.append(value))
    plugin_controller = object()

    controller.plugin_controller = plugin_controller

    assert controller.plugin_controller is plugin_controller
    assert registered == [plugin_controller]


def test_welcomescreen_controller_property_emits_controller_registered():
    controller = MainController.__new__(MainController)
    GObjectWrapper.__init__(controller)
    registered = []
    controller.connect('controller-registered', lambda _c, value: registered.append(value))
    welcomescreen_controller = object()

    controller.welcomescreen_controller = welcomescreen_controller

    assert controller.welcomescreen_controller is welcomescreen_controller
    assert registered == [welcomescreen_controller]


# quit()'s remaining branches - no dialogs open, in each case #

def test_quit_saves_first_when_the_user_confirms_the_save_prompt(monkeypatch):
    monkeypatch.setattr(Gtk.Window, 'list_toplevels', lambda: [])
    calls = []
    controller = MainController.__new__(MainController)
    GObjectWrapper.__init__(controller)
    controller._store_controller = SimpleNamespace(is_modified=lambda: True)
    controller.view = SimpleNamespace(
        show_save_confirm_dialog=lambda: 'save',
        hide=lambda: calls.append('hide'),
        quit=lambda: calls.append('view-quit'),
    )
    controller.save_file = lambda: calls.append('saved') or True
    controller._plugin_controller = None
    controller.connect('quit', lambda *_: calls.append('quit-signal'))

    result = controller.quit()

    assert result is False
    assert calls == ['saved', 'hide', 'quit-signal', 'view-quit']


def test_quit_stays_open_when_the_save_itself_fails(monkeypatch):
    monkeypatch.setattr(Gtk.Window, 'list_toplevels', lambda: [])
    controller = MainController.__new__(MainController)
    controller._store_controller = SimpleNamespace(is_modified=lambda: True)
    controller.view = SimpleNamespace(show_save_confirm_dialog=lambda: 'save')
    controller.save_file = lambda: False

    assert controller.quit() is False


def test_quit_stays_open_when_the_user_backs_out_without_discarding(monkeypatch):
    monkeypatch.setattr(Gtk.Window, 'list_toplevels', lambda: [])
    controller = MainController.__new__(MainController)
    controller._store_controller = SimpleNamespace(is_modified=lambda: True)
    controller.view = SimpleNamespace(show_save_confirm_dialog=lambda: 'cancel')

    assert controller.quit() is True


def test_quit_discards_changes_and_shuts_down(monkeypatch):
    monkeypatch.setattr(Gtk.Window, 'list_toplevels', lambda: [])
    calls = []
    controller = MainController.__new__(MainController)
    GObjectWrapper.__init__(controller)
    controller._store_controller = SimpleNamespace(is_modified=lambda: True)
    controller.view = SimpleNamespace(
        show_save_confirm_dialog=lambda: 'discard',
        hide=lambda: calls.append('hide'),
        quit=lambda: calls.append('view-quit'),
    )
    controller._plugin_controller = None
    controller.connect('quit', lambda *_: calls.append('quit-signal'))

    result = controller.quit()

    assert result is False
    assert calls == ['hide', 'quit-signal', 'view-quit']


def test_quit_shuts_down_the_plugin_controller_when_one_is_registered(monkeypatch):
    monkeypatch.setattr(Gtk.Window, 'list_toplevels', lambda: [])
    calls = []
    controller = MainController.__new__(MainController)
    GObjectWrapper.__init__(controller)
    controller._store_controller = SimpleNamespace(is_modified=lambda: False)
    controller.view = SimpleNamespace(hide=lambda: None, quit=lambda: None)
    controller._plugin_controller = SimpleNamespace(shutdown=lambda: calls.append('shutdown'))

    controller.quit()

    assert calls == ['shutdown']


def test_quit_forces_past_unsaved_changes(monkeypatch):
    monkeypatch.setattr(Gtk.Window, 'list_toplevels', lambda: [])
    calls = []
    controller = MainController.__new__(MainController)
    GObjectWrapper.__init__(controller)
    controller._store_controller = SimpleNamespace(is_modified=lambda: True)
    controller.view = SimpleNamespace(
        hide=lambda: calls.append('hide'),
        quit=lambda: calls.append('view-quit'),
    )
    controller._plugin_controller = None
    controller.connect('quit', lambda *_: calls.append('quit-signal'))

    result = controller.quit(force=True)

    assert result is False
    assert calls == ['hide', 'quit-signal', 'view-quit']
