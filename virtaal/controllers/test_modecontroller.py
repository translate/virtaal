#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.


from types import SimpleNamespace

from virtaal.controllers.modecontroller import ModeController


def _controller(**availability):
    controller = ModeController.__new__(ModeController)
    controller.modes = {
        name: SimpleNamespace(display_name=name.title(), is_available=lambda available=available: available)
        for name, available in availability.items()
    }
    controller.unavailable = None
    controller.view = SimpleNamespace(set_unavailable_modes=lambda names: setattr(controller, 'unavailable', names))
    return controller


def test_update_mode_availability_greys_out_modes_with_nothing_to_navigate():
    controller = _controller(default=True, incomplete=False, search=True)

    controller.update_mode_availability()

    assert controller.unavailable == ['Incomplete']


def test_store_loaded_or_saved_updates_mode_availability():
    controller = _controller(default=True, incomplete=False)

    controller._on_store_changed(None)

    assert controller.unavailable == ['Incomplete']


def test_store_closed_makes_every_mode_available_again():
    controller = _controller(default=True, incomplete=False)
    controller.select_default_mode = lambda: None
    controller.view.hide = lambda: None
    controller.unavailable = ['Incomplete']

    controller._on_store_closed(None)

    assert controller.unavailable == []


def _selecting_controller(**availability):
    controller = _controller(**availability)
    controller.default_mode_name = 'default'
    controller.modenames = {name: name.title() for name in availability}
    controller.current_mode = None
    selected, emitted = [], []
    for name, mode in controller.modes.items():
        mode.name = name
        mode.widgets = []
        mode.selected = lambda name=name: selected.append(name)
    controller.view.select_mode = lambda displayname: None
    controller.view.show = lambda: None
    controller.emit = lambda signal, mode: emitted.append(mode.name)
    return controller, selected, emitted


def test_select_mode_selects_an_available_mode():
    controller, selected, emitted = _selecting_controller(default=True, incomplete=True)

    controller.select_mode(controller.modes['incomplete'])

    assert controller.current_mode.name == 'incomplete'
    assert (selected, emitted) == (['incomplete'], ['incomplete'])


def test_select_mode_selects_the_default_mode_instead_of_an_unavailable_one():
    # Selecting Incomplete with nothing incomplete used to re-enter
    # select_mode() from the mode's own selected() (#3763).
    controller, selected, emitted = _selecting_controller(default=True, incomplete=False)

    controller.select_mode(controller.modes['incomplete'])

    assert controller.current_mode.name == 'default'
    assert (selected, emitted) == (['default'], ['default'])
