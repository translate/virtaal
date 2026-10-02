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
        name: SimpleNamespace(
            display_name=name.title(),
            is_available=lambda available=available: available,
            circular=name in ('search', 'qualitycheck'),
        )
        for name, available in availability.items()
    }
    controller.current_mode = None
    controller.main_controller = SimpleNamespace(
        store_controller=SimpleNamespace(cursor=SimpleNamespace(circular=True)),
    )
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
        mode.unselected = lambda: None
    controller.view.remove_mode_widgets = lambda widgets: None
    controller.view.select_mode = lambda displayname: None
    controller.view.show = lambda: None
    controller.view.set_context_sensitive = lambda sensitive: setattr(controller, 'context_sensitive', sensitive)
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


def test_select_mode_sets_whether_the_cursor_wraps():
    # Search and checks step through hits; other modes are the document
    # and stop at its ends (#3789).
    controller, _selected, _emitted = _selecting_controller(default=True, search=True, qualitycheck=True)
    cursor = controller.main_controller.store_controller.cursor

    controller.select_mode(controller.modes['default'])
    assert cursor.circular is False

    controller.select_mode(controller.modes['search'])
    assert cursor.circular is True

    controller.select_mode(controller.modes['qualitycheck'])
    assert cursor.circular is True


def test_a_newly_loaded_store_cursor_wraps_as_the_current_mode_does():
    controller = _controller(default=True, search=True)
    controller.current_mode = controller.modes['search']
    cursor = SimpleNamespace(circular=False)
    controller.main_controller.store_controller.cursor = cursor

    controller._on_store_changed(None)

    assert cursor.circular is True


def test_context_only_applies_outside_the_default_mode():
    controller, _selected, _emitted = _selecting_controller(default=True, incomplete=True)

    controller.select_mode(controller.modes['incomplete'])
    assert controller.context_sensitive is True

    controller.select_mode(controller.modes['default'])
    assert controller.context_sensitive is False


def test_context_selected_is_passed_to_the_store_view_then_announced():
    controller = _controller(default=True)
    events = []
    controller.main_controller = SimpleNamespace(
        store_controller=SimpleNamespace(view=SimpleNamespace(set_context=lambda c: events.append(('rows', c)))))
    controller.emit = lambda signal, context: events.append((signal, context))

    controller._on_context_selected(None, 2)

    assert events == [('rows', 2), ('context-selected', 2)]


# Choosing a mode from the list (#1925) #

def _choosing_controller(monkeypatch, mode):
    controller = _controller(default=True)
    controller._ignore_mode_change = False
    controller._mode_list_just_closed = False
    controller.get_mode_by_display_name = lambda name: mode
    controller.select_mode = lambda chosen: setattr(controller, 'current_mode', chosen)
    events = []
    target = SimpleNamespace(grab_focus=lambda: events.append('focus unit'))
    controller.main_controller = SimpleNamespace(
        unit_controller=SimpleNamespace(view=SimpleNamespace(targets=[target], focused_target_n=None)),
        store_controller=SimpleNamespace(get_store=lambda: object()),
    )
    idles = []
    monkeypatch.setattr('virtaal.controllers.modecontroller.GLib.idle_add', idles.append)

    def run_idles():
        while idles:
            idles.pop(0)()
    return controller, events, run_idles


def _choose_from_list(controller, name):
    # GTK closes the list, then reports the change.
    controller._on_mode_list_shown(SimpleNamespace(props=SimpleNamespace(popup_shown=False)), None)
    controller._on_mode_selected(None, name)


def test_choosing_a_mode_from_the_list_goes_to_the_unit(monkeypatch):
    controller, events, run_idles = _choosing_controller(monkeypatch, SimpleNamespace(widgets=[]))

    _choose_from_list(controller, 'Incomplete')
    run_idles()

    assert events == ['focus unit']


def test_arrowing_through_the_closed_selector_leaves_focus_there(monkeypatch):
    controller, events, run_idles = _choosing_controller(monkeypatch, SimpleNamespace(widgets=[]))

    controller._on_mode_selected(None, 'Incomplete')
    run_idles()

    assert events == []


def test_a_change_long_after_the_list_closed_isnt_a_choice_from_it(monkeypatch):
    controller, events, run_idles = _choosing_controller(monkeypatch, SimpleNamespace(widgets=[]))
    controller.current_mode = SimpleNamespace(widgets=['search entry'])  # what the list closed on
    controller._on_mode_list_shown(SimpleNamespace(props=SimpleNamespace(popup_shown=False)), None)
    run_idles()

    controller._on_mode_selected(None, 'Incomplete')
    run_idles()

    assert events == []


def test_closing_the_list_without_a_change_carries_on_with_the_current_mode(monkeypatch):
    # Choosing the mode that's already selected, or Escape.
    controller, events, run_idles = _choosing_controller(monkeypatch, SimpleNamespace(widgets=[]))
    controller.current_mode = SimpleNamespace(widgets=[])

    controller._on_mode_list_shown(SimpleNamespace(props=SimpleNamespace(popup_shown=False)), None)
    run_idles()

    assert events == ['focus unit']


def test_a_choice_from_the_list_carries_on_only_once(monkeypatch):
    controller, events, run_idles = _choosing_controller(monkeypatch, SimpleNamespace(widgets=[]))

    _choose_from_list(controller, 'Incomplete')
    run_idles()

    assert events == ['focus unit']


def test_choosing_a_mode_with_a_menu_opens_it_then_goes_to_the_unit(monkeypatch):
    class _Menu:
        def connect(self, signal, handler):
            self.closed = handler
            return 1

        def disconnect(self, handler_id):
            pass
    menu = _Menu()
    button = SimpleNamespace(menu=menu, get_sensitive=lambda: True)
    button.set_active = lambda active: events.append('menu open')
    controller, events, run_idles = _choosing_controller(
        monkeypatch, SimpleNamespace(widgets=[button], btn_popup=button))

    _choose_from_list(controller, 'Quality Checks')
    run_idles()
    assert events == ['menu open']

    menu.closed(menu)  # a check chosen with Enter, or Escape
    run_idles()
    assert events == ['menu open', 'focus unit']


def test_choosing_search_leaves_focus_to_its_entry(monkeypatch):
    controller, events, run_idles = _choosing_controller(monkeypatch, SimpleNamespace(widgets=['entry']))

    _choose_from_list(controller, 'Search')
    run_idles()

    assert events == []


def test_focus_translation_without_a_file_does_nothing():
    controller = _controller(default=True)
    controller.main_controller = SimpleNamespace(
        unit_controller=SimpleNamespace(view=SimpleNamespace(targets=[], focused_target_n=None)),
        store_controller=SimpleNamespace(get_store=lambda: None),
    )

    controller._focus_translation()  # must not raise
