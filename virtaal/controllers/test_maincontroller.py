#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import GLib, Gtk

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
