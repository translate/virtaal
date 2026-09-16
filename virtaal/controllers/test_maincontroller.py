#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk

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
