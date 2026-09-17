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
