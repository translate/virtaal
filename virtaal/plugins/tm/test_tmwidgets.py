#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import time
from types import SimpleNamespace

import pytest
from gi.repository import Gdk, Gtk

from virtaal.common import pan_app
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


@pytest.mark.parametrize('lang, expected', [
    ('en', '75%'),
    ('fr', '75\u00a0%'),
    ('tr', '%75'),
    ('bn_IN', '৭৫%'),
])
def test_percent_data_func_shows_the_quality_as_the_ui_language_writes_it(monkeypatch, lang, expected):
    monkeypatch.setattr(pan_app, 'ui_language', lang)

    properties = _percent({'quality': 75, 'source': 'a', 'target': 'b'})

    assert properties['value'] == 75
    assert properties['text'] == expected


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


def _make_source_and_target(position, height=WINDOW_HEIGHT):
    """Source and target, each in its own ScrolledWindow as in the real unit
    view, pinned to the 'top' or 'bottom' of the window by a filler."""
    window = Gtk.Window()
    window.set_decorated(False)
    vbox = Gtk.VBox()
    textviews = []
    for _ in range(2):
        textview = Gtk.TextView()
        textview.set_size_request(400, 30)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        scrolled.add(textview)
        textviews.append((textview, scrolled))
    (source, source_scrolled), (target, target_scrolled) = textviews
    target.selector_textbox = source
    if position == 'bottom':
        vbox.pack_start(Gtk.Label(), True, True, 0)
    vbox.pack_start(source_scrolled, False, False, 0)
    vbox.pack_start(target_scrolled, False, False, 0)
    if position == 'top':
        vbox.pack_start(Gtk.Label(), True, True, 0)
    window.add(vbox)
    window.set_default_size(400, height)
    window.show_all()
    _process_events()
    window.move(*_workarea_origin(target))
    _process_events()
    return window, source, target


def _workarea_origin(widget):
    display = Gdk.Display.get_default()
    workarea = display.get_monitor_at_window(widget.get_window(Gtk.TextWindowType.WIDGET)).get_workarea()
    return workarea.x + 10, workarea.y + 10


def _popup_span(tmwindow):
    popup_window = tmwindow.get_window()
    top = popup_window.get_root_origin().y
    return top, top + popup_window.get_height()


def _top(textview):
    return textview.get_window(Gtk.TextWindowType.WIDGET).get_origin().y


def _bottom(textview):
    return _top(textview) + textview.get_parent().get_allocation().height


def _fake_view():
    """Just enough of a TMView for the match renderer to size real rows."""
    lang = SimpleNamespace(source_lang=SimpleNamespace(code='en'), target_lang=SimpleNamespace(code='af'))
    return SimpleNamespace(
        get_target_width=lambda: 400,
        controller=SimpleNamespace(main_controller=SimpleNamespace(lang_controller=lang)))


def _make_tmwindow_with_matches(n=1, show=True):
    tmwindow = TMWindow(_fake_view())
    for i in range(n):
        match = {'quality': 90 - i, 'tmsource': 'Current file', 'query_str': 'query',
                 'source': f'source text {i}', 'target': f'target text {i}'}
        tmwindow.liststore.append([match, f'match {i}'])
    tmwindow.treeview.columns_autosize()
    if show:
        tmwindow.show_all()
        _process_events()
    return tmwindow


def test_rows_height_is_known_before_the_window_is_shown():
    # update_geometry() places the window before it is first shown.
    tmwindow = _make_tmwindow_with_matches(n=3, show=False)
    before = tmwindow.rows_height()

    tmwindow.show_all()
    _process_events()

    assert before > 3 * 20
    assert tmwindow.rows_height() == before

    tmwindow.destroy()


def test_update_geometry_pops_down_when_there_is_room_below():
    window, _source, target = _make_source_and_target('top')
    tmwindow = _make_tmwindow_with_matches()

    tmwindow.update_geometry(target)
    _process_events()

    top, _ = _popup_span(tmwindow)
    assert top >= _bottom(target)

    tmwindow.destroy()
    window.destroy()


def test_update_geometry_flips_above_the_source_when_there_is_no_room_below():
    window, source, target = _make_source_and_target('bottom')
    tmwindow = _make_tmwindow_with_matches(n=3)

    tmwindow.update_geometry(target)
    _process_events()

    _, bottom = _popup_span(tmwindow)
    assert bottom <= _top(source)

    tmwindow.destroy()
    window.destroy()


# Too many matches to fit above or below a unit in a short window: the
# popup must shrink rather than cover the unit.

def test_update_geometry_shrinks_above_when_neither_side_fits():
    window, source, target = _make_source_and_target('bottom', height=250)
    tmwindow = _make_tmwindow_with_matches(n=20)
    assert tmwindow.rows_height() > tmwindow.MAX_HEIGHT

    tmwindow.update_geometry(target)
    _process_events()

    top, bottom = _popup_span(tmwindow)
    assert bottom <= _top(source)
    assert bottom - top < tmwindow.MAX_HEIGHT

    tmwindow.destroy()
    window.destroy()


def test_update_geometry_shrinks_below_when_neither_side_fits():
    window, _source, target = _make_source_and_target('top', height=250)
    tmwindow = _make_tmwindow_with_matches(n=20)
    assert tmwindow.rows_height() > tmwindow.MAX_HEIGHT

    tmwindow.update_geometry(target)
    _process_events()

    top, bottom = _popup_span(tmwindow)
    assert top >= _bottom(target)
    assert bottom - top < tmwindow.MAX_HEIGHT

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


def test_spare_width_goes_to_the_matches_not_the_tm_source_column():
    # update_geometry() sizes the window from the TM Source column's
    # width; if that column took the spare width, each update would make
    # the window wider. GTK gives spare width to the last column unless
    # another one expands.
    tmwindow = TMWindow(None)

    assert tmwindow.tvc_match.get_expand() is True
    assert tmwindow.tvc_tm_source.get_expand() is False


def test_update_geometry_shrinks_back_when_the_target_narrows():
    # #4149: after fullscreen and back, the Matches column kept its
    # fullscreen width.
    window, _source, target = _make_source_and_target('top')
    tmwindow = TMWindow(_fake_view())
    tmwindow.view.get_target_width = lambda: target.get_parent().get_allocation().width
    tmwindow.liststore.append([{'quality': 90, 'tmsource': 'Current file', 'query_str': 'query',
                                'source': 'source text', 'target': 'target text'}, 'match'])
    tmwindow.show_all()
    _process_events()

    def update_at(window_width):
        window.resize(window_width, WINDOW_HEIGHT)
        for _ in range(100):
            _process_events()
            if target.get_parent().get_allocation().width == window_width:
                break
            time.sleep(0.01)
        tmwindow.update_geometry(target)
        for _ in range(10):
            _process_events()
            time.sleep(0.01)
        return tmwindow.get_window().get_width(), tmwindow.tvc_match.get_width()

    update_at(400)
    wide_width, wide_match_width = update_at(900)
    width, match_width = update_at(400)

    assert width < wide_width - 400
    assert match_width < wide_match_width - 400

    tmwindow.destroy()
    window.destroy()
