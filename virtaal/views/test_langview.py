#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.views.langview import LanguageView


def test_set_popupbutton_fg_accepts_a_colour():
    # A malformed generated CSS string raises Gtk.CssProvider's own
    # GLib.GError - this is really a check that the string built here
    # is valid CSS, not just that the call completes.
    view = LanguageView.__new__(LanguageView)
    view.popupbutton = Gtk.Button()
    view._popupbutton_fg_provider = None

    view._set_popupbutton_fg('#f66')


def test_set_popupbutton_fg_removes_its_previous_provider_on_a_later_call(monkeypatch):
    """notify_same_langs()/notify_diff_langs() toggle this on every
        cursor change - each call used to only ever add a new
        provider, accumulating one per toggle, never freed."""
    view = LanguageView.__new__(LanguageView)
    view.popupbutton = Gtk.Button()
    view._popupbutton_fg_provider = None

    removed = []
    style = view.popupbutton.get_style_context()
    monkeypatch.setattr(style, 'remove_provider', lambda provider: removed.append(provider))

    view._set_popupbutton_fg('#f66')
    first_provider = view._popupbutton_fg_provider
    view._set_popupbutton_fg(None)

    assert removed == [first_provider]
    assert view._popupbutton_fg_provider is None
