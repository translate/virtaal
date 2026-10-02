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
