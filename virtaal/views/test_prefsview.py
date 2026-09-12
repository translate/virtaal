#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.views.baseview import BaseView
from virtaal.views.prefsview import PreferencesView


def _load_widgets():
    view = PreferencesView.__new__(PreferencesView)
    gui = BaseView.load_builder_file(["virtaal", "virtaal.ui"], root='PreferencesDlg', domain="virtaal")
    view._widgets = {
        'scrwnd_placeables': gui.get_object('scrwnd_placeables'),
        'scrwnd_plugins': gui.get_object('scrwnd_plugins'),
    }
    return view


def test_plugins_page_scrolled_window_propagates_natural_width():
    # A plugin's inline "Configure..." button got clipped/hidden - a
    # ScrolledWindow doesn't request its child's actual width by
    # default, it just shrinks it instead.
    view = _load_widgets()

    view._init_plugins_page()

    assert view._widgets['scrwnd_plugins'].get_property('propagate-natural-width')


def test_placeables_page_scrolled_window_propagates_natural_width():
    view = _load_widgets()

    view._init_placeables_page()

    assert view._widgets['scrwnd_placeables'].get_property('propagate-natural-width')


def test_plugins_page_scrolled_window_is_not_focusable():
    # The .ui file marks it focusable, which swallows Tab/Down meant
    # for the list inside it (confirmed live: Right-arrow tab-browsing
    # got stuck, and Down from the tab strip did nothing).
    view = _load_widgets()

    view._init_plugins_page()

    assert not view._widgets['scrwnd_plugins'].get_can_focus()


def test_placeables_page_scrolled_window_is_not_focusable():
    view = _load_widgets()

    view._init_placeables_page()

    assert not view._widgets['scrwnd_placeables'].get_can_focus()
