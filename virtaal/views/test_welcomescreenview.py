#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from gi.repository import Gtk

from virtaal.views import baseview, welcomescreenview
from virtaal.views.welcomescreenview import WelcomeScreenView


@pytest.fixture(autouse=True)
def _fresh_builder_cache(monkeypatch):
    # WelcomeScreenView.__init__ loads real widgets from virtaal.ui via
    # the cached builder - a cached one would hand back the very same
    # WelcomeScreen object (already reparented by a previous test's
    # construction) across tests.
    monkeypatch.setattr(baseview, '_builders', {})


def _real_builder():
    builder = Gtk.Builder()
    builder.add_from_file('share/virtaal/virtaal.ui')
    return builder


def _fake_controller():
    calls = SimpleNamespace(open_file=[], open_recent=[], open_tutorial=[],
                             open_cheatsheat=[], open_bug_report=[], try_open_link=[])
    controller = SimpleNamespace(
        main_controller=SimpleNamespace(view=SimpleNamespace(gui=_real_builder())),
        MAX_RECENT=5,
        open_file=lambda: calls.open_file.append(True),
        open_recent=lambda n: calls.open_recent.append(n),
        open_tutorial=lambda: calls.open_tutorial.append(True),
        open_cheatsheat=lambda: calls.open_cheatsheat.append(True),
        open_bug_report=lambda: calls.open_bug_report.append(True),
        try_open_link=lambda name: calls.try_open_link.append(name),
    )
    controller.calls = calls
    return controller


def _make_view():
    return WelcomeScreenView(_fake_controller())


def _recent_items(count):
    return [{'name': 'Item %d' % i, 'uri': 'file:///item%d' % i} for i in range(count)]


# __init__() / set_banner() #

def test_init_builds_a_real_welcome_screen_wired_to_its_parent():
    view = _make_view()

    assert isinstance(view.widget, Gtk.ScrolledWindow)
    assert view.parent_widget is view.controller.main_controller.view.gui.get_object('vbox_main')


def test_init_connects_button_clicks_to_the_controller():
    view = _make_view()

    view.widget.widgets['buttons']['tutorial'].clicked()

    assert view.controller.calls.open_tutorial == [True]


def test_set_banner_uses_the_rtl_banner_when_the_widget_is_rtl():
    view = _make_view()
    calls = []
    view.widget.set_banner_image = calls.append
    view.widget.set_direction(Gtk.TextDirection.RTL)

    view.set_banner()

    assert calls == [welcomescreenview.get_abs_data_filename(['virtaal', 'welcome_screen_banner_rtl.png'])]


def test_set_banner_uses_the_plain_banner_for_ltr():
    view = _make_view()
    calls = []
    view.widget.set_banner_image = calls.append
    view.widget.set_direction(Gtk.TextDirection.LTR)

    view.set_banner()

    assert calls == [welcomescreenview.get_abs_data_filename(['virtaal', 'welcome_screen_banner.png'])]


def test_set_banner_uses_the_arabic_banner_regardless_of_direction(monkeypatch):
    view = _make_view()
    calls = []
    view.widget.set_banner_image = calls.append
    monkeypatch.setattr(welcomescreenview, 'ui_language', 'ar')
    view.widget.set_direction(Gtk.TextDirection.LTR)

    view.set_banner()

    assert calls == [welcomescreenview.get_abs_data_filename(['virtaal', 'welcome_screen_banner_ar.png'])]


# hide() / show() #

def test_hide_hides_the_widget_and_detaches_it_from_its_parent():
    view = _make_view()
    view.show()

    view.hide()

    assert not view.widget.get_visible()
    assert view.widget.get_parent() is None


def test_hide_tolerates_a_widget_that_was_never_shown():
    view = _make_view()

    view.hide()  # must not raise - widget has no parent to remove from

    assert not view.widget.get_visible()


def test_show_adds_the_widget_to_its_parent(monkeypatch):
    monkeypatch.setattr(welcomescreenview.GLib, 'idle_add', lambda *a, **k: None)
    view = _make_view()

    view.show()

    assert view.widget.get_parent() is view.parent_widget
    assert view.widget.get_visible()


def test_show_reparents_a_widget_already_attached_elsewhere(monkeypatch):
    monkeypatch.setattr(welcomescreenview.GLib, 'idle_add', lambda *a, **k: None)
    view = _make_view()
    other_parent = Gtk.Box()
    other_parent.add(view.widget)

    view.show()

    assert view.widget.get_parent() is view.parent_widget
    assert view.widget not in other_parent.get_children()


def test_show_schedules_the_width_calculation(monkeypatch):
    # Constructed before patching idle_add - WelcomeScreen.__init__'s own
    # _init_feature_view() schedules an unrelated idle callback too
    # (harmless left to actually run for real, since nothing here pumps
    # a main loop), so only show()'s own call is captured below.
    view = _make_view()
    calls = []
    monkeypatch.setattr(welcomescreenview.GLib, 'idle_add', lambda func, *a, **k: calls.append((func, a)))

    view.show()

    assert len(calls) == 1
    func, args = calls[0]
    func(*args)  # must not raise on an unrealized/zero-allocation widget


def test_show_focuses_open(monkeypatch):
    monkeypatch.setattr(welcomescreenview.GLib, 'idle_add', lambda *a, **k: None)
    view = _make_view()

    view.show()

    assert view.widget.widgets['buttons']['open'].is_focus()


# update_recent_buttons() #

def test_update_recent_buttons_hides_the_frame_when_there_are_no_items():
    view = _make_view()
    view.widget.gui.get_object('frame_recent').show_all()

    view.update_recent_buttons([])

    assert not view.widget.gui.get_object('frame_recent').get_visible()


def test_update_recent_buttons_fills_in_each_button(monkeypatch):
    view = _make_view()
    monkeypatch.setattr(welcomescreenview, 'get_abs_data_filename', lambda parts: '/icons/x-translation.png')
    items = _recent_items(2)

    view.update_recent_buttons(items)

    assert view.widget.gui.get_object('frame_recent').get_visible()
    for i, item in enumerate(items):
        button = view.widget.widgets['buttons']['recent%d' % (i + 1)]
        label = button.get_child().get_children()[1]
        assert item['name'] in label.get_text()
        assert button.get_tooltip_text() == item['uri']
        assert button.props.visible is True


def test_update_recent_buttons_escapes_special_characters_in_the_name(monkeypatch):
    view = _make_view()
    monkeypatch.setattr(welcomescreenview, 'get_abs_data_filename', lambda parts: '/icons/x-translation.png')

    view.update_recent_buttons([{'name': 'A & B <C>', 'uri': 'file:///x'}])

    label = view.widget.widgets['buttons']['recent1'].get_child().get_children()[1]
    assert label.get_text() == 'A & B <C>'


def test_update_recent_buttons_hides_the_unused_trailing_buttons(monkeypatch):
    view = _make_view()
    monkeypatch.setattr(welcomescreenview, 'get_abs_data_filename', lambda parts: '/icons/x-translation.png')

    view.update_recent_buttons(_recent_items(2))

    for i in range(3, 6):
        assert view.widget.widgets['buttons']['recent%d' % i].props.visible is False


# _on_button_clicked() #

def test_on_button_clicked_open():
    view = _make_view()

    view._on_button_clicked(None, 'open')

    assert view.controller.calls.open_file == [True]


def test_on_button_clicked_recent_parses_the_trailing_number():
    view = _make_view()

    view._on_button_clicked(None, 'recent3')

    assert view.controller.calls.open_recent == [3]


def test_on_button_clicked_tutorial():
    view = _make_view()

    view._on_button_clicked(None, 'tutorial')

    assert view.controller.calls.open_tutorial == [True]


def test_on_button_clicked_cheatsheet():
    view = _make_view()

    view._on_button_clicked(None, 'cheatsheet')

    assert view.controller.calls.open_cheatsheat == [True]


def test_on_button_clicked_report_bug():
    view = _make_view()

    view._on_button_clicked(None, 'report_bug')

    assert view.controller.calls.open_bug_report == [True]


def test_on_button_clicked_anything_else_tries_to_open_it_as_a_link():
    view = _make_view()

    view._on_button_clicked(None, 'https://example.com')

    assert view.controller.calls.try_open_link == ['https://example.com']
