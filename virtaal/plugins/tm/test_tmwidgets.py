#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gdk, Gtk

from virtaal.plugins.tm.tmwidgets import TMSourceColRenderer, TMWindow


class _FakeCellRenderer:
    def __init__(self):
        self.properties = {}

    def set_property(self, name, value):
        self.properties[name] = value


def _percent(match_data):
    tree_model = type('M', (), {'get_value': staticmethod(lambda iter, col: match_data)})()
    cell_renderer = _FakeCellRenderer()
    TMWindow._percent_data_func(None, None, cell_renderer, tree_model, None, None)
    return cell_renderer.properties


def test_percent_data_func_shows_the_exact_quality_within_range():
    properties = _percent({'quality': 75, 'source': 'a', 'target': 'b'})
    assert properties['value'] == 75
    assert properties['text'] == '75%'


def test_percent_data_func_shows_a_question_mark_for_a_match_with_no_quality():
    properties = _percent({'source': 'a', 'target': 'b'})
    assert properties['value'] == 0
    assert properties['text'] == '?'


# TMSourceColRenderer: no-op when the match has no tmsource to show
# (e.g. a plain MT suggestion).

def test_do_get_size_returns_zero_without_a_tm_source():
    renderer = TMSourceColRenderer(view=None)
    renderer.matchdata = {'source': 'a'}

    assert renderer.do_get_size(widget=None, cell_area=None) == (0, 0, 0, 0)


def test_do_render_does_nothing_without_a_tm_source():
    renderer = TMSourceColRenderer(view=None)
    renderer.matchdata = {'source': 'a'}

    renderer.do_render(window=None, widget=None, _background_area=None, cell_area=None, _flags=None)


# update_geometry(): real widgets, real positions - translate/virtaal#1366
# (a unit rendered near the bottom of the screen could push the popup
# off-screen, or, once clamped, over the widget it's anchored to).

def _process_events():
    while Gtk.events_pending():
        Gtk.main_iteration()


# Tall enough to be representative of a real (large/maximized) Virtaal
# window - deliberately much taller than the popup itself, so "is there
# room" is being tested by the target's position within the window, not
# by the window being too short to ever fit the popup at all.
WINDOW_HEIGHT = 700


def _make_source_and_target(near_bottom):
    """near_bottom=False packs a filler *after* source/target, pinning
    them near the top (room below); near_bottom=True packs it *before*,
    pinning them near the bottom (no room below) - within the same
    realistically-tall window either way."""
    window = Gtk.Window()
    window.set_decorated(False)
    vbox = Gtk.VBox()
    filler = Gtk.Label()
    source = Gtk.TextView()
    source.set_size_request(400, 30)
    target = Gtk.TextView()
    target.set_size_request(400, 30)
    target.selector_textbox = source
    if near_bottom:
        vbox.pack_start(filler, True, True, 0)
    vbox.pack_start(source, False, False, 0)
    vbox.pack_start(target, False, False, 0)
    if not near_bottom:
        vbox.pack_start(filler, True, True, 0)
    window.add(vbox)
    window.set_default_size(400, WINDOW_HEIGHT)
    window.show_all()
    _process_events()
    return window, source, target


def _make_tmwindow_with_matches(n=1):
    tmwindow = TMWindow(None)
    for i in range(n):
        tmwindow.liststore.append([{'quality': 90 - i, 'tmsource': 'Current file'}, f'match {i}'])
    tmwindow.treeview.columns_autosize()
    tmwindow.show_all()
    _process_events()
    return tmwindow


def test_update_geometry_pops_down_when_there_is_room_below():
    window, _source, target = _make_source_and_target(near_bottom=False)
    display = Gdk.Display.get_default()
    monitor = display.get_monitor_at_window(target.get_window(Gtk.TextWindowType.WIDGET))
    workarea = monitor.get_workarea()
    window.move(workarea.x + 10, workarea.y + 10)
    _process_events()

    tmwindow = _make_tmwindow_with_matches()
    target_origin = target.get_window(Gtk.TextWindowType.WIDGET).get_origin()

    tmwindow.update_geometry(target)
    _process_events()

    popup_origin = tmwindow.get_window().get_root_origin()
    assert popup_origin.y > target_origin.y

    tmwindow.destroy()
    window.destroy()


def test_update_geometry_flips_above_the_source_when_there_is_no_room_below():
    window, source, target = _make_source_and_target(near_bottom=True)
    display = Gdk.Display.get_default()
    monitor = display.get_monitor_at_window(target.get_window(Gtk.TextWindowType.WIDGET))
    workarea = monitor.get_workarea()
    window.move(workarea.x + 10, workarea.y + 10)
    _process_events()

    tmwindow = _make_tmwindow_with_matches(n=3)
    source_origin = source.get_window(Gtk.TextWindowType.WIDGET).get_origin()

    tmwindow.update_geometry(target)
    _process_events()

    popup_window = tmwindow.get_window()
    popup_origin = popup_window.get_root_origin()
    popup_bottom = popup_origin.y + popup_window.get_height()

    # Must not overlap the source text it's meant to leave visible.
    assert popup_bottom <= source_origin.y
    # Must not overflow past the bottom of the usable screen area either.
    assert popup_bottom <= workarea.y + workarea.height

    tmwindow.destroy()
    window.destroy()


def test_update_geometry_sizes_the_popup_from_the_real_theme_border(monkeypatch):
    # rows_height() is fixed here rather than measured from real rows -
    # its own real value isn't stable across a full suite run (a known,
    # separate GTK cross-test state issue - #3738), and isn't what this
    # test is about. What matters here is that the *border* added on
    # top of it is queried from the real theme, not a hardcoded guess.
    tmwindow = TMWindow(None)
    monkeypatch.setattr(tmwindow, 'rows_height', lambda: 100)
    tmwindow.show_all()
    _process_events()

    window = Gtk.Window()
    target = Gtk.TextView()
    target.set_size_request(200, 30)
    window.add(target)
    window.show_all()
    _process_events()

    border = tmwindow.scrolled_window.get_style_context().get_border(Gtk.StateFlags.NORMAL)
    expected_height = 100 + border.top + border.bottom

    tmwindow.update_geometry(target)
    _process_events()

    assert tmwindow.get_window().get_height() == expected_height

    tmwindow.destroy()
    window.destroy()
