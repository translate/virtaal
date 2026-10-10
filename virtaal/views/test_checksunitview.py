#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import Gtk

from virtaal.views.checksunitview import ChecksUnitView


def _make_view():
    main_window = Gtk.Window()
    store_controller = SimpleNamespace(connect=lambda *args: None)
    main_controller = SimpleNamespace(
        view=SimpleNamespace(
            main_window=main_window,
            gui=SimpleNamespace(get_object=lambda name: Gtk.MenuItem())),
        store_controller=store_controller,
        unit_controller=SimpleNamespace(view=SimpleNamespace(sources=[Gtk.Label()])))
    controller = SimpleNamespace(main_controller=main_controller, get_check_name=lambda name: name)
    view = ChecksUnitView(controller)
    main_window.add(view.btn_checks)
    main_window.show_all()
    return view


def _update(view, failures):
    view.update(failures)
    btn = view.btn_checks
    if btn._show_tick_id:
        btn.remove_tick_callback(btn._show_tick_id)
        while btn._show_tick_id:
            btn._on_show_tick(btn, None)


def _rows(view):
    return [tuple(row) for row in view.lst_checks]


def test_failures_fill_the_popup_and_the_button():
    view = _make_view()
    view.btn_checks.set_active(True)

    _update(view, {'xmltags': 'Different XML tags'})

    assert view.btn_checks.is_popup_visible
    assert _rows(view) == [('xmltags', 'Different XML tags')]
    assert view.lbl_btnchecks.get_text() == 'xmltags'


def test_no_failures_pops_up_nothing_but_keeps_the_button_pressed():
    # Expanded checks with nothing to report show no "No issues" text.
    view = _make_view()
    view.btn_checks.set_active(True)
    _update(view, {'xmltags': 'Different XML tags'})

    _update(view, {})

    assert not view.btn_checks.is_popup_visible
    assert view.btn_checks.get_active()
    assert view.btn_checks.get_opacity() == 0

    _update(view, {'xmltags': 'Different XML tags'})

    assert view.btn_checks.is_popup_visible
    assert view.btn_checks.get_opacity() == 1


def test_pressing_the_button_before_any_failures_pops_up_nothing():
    view = _make_view()

    view.btn_checks.set_active(True)

    assert not view.btn_checks.is_popup_visible


def test_untranslated_alone_counts_as_no_failures():
    view = _make_view()
    view.btn_checks.set_active(True)

    _update(view, {'untranslated': 'Untranslated'})

    assert not view.btn_checks.is_popup_visible


def test_new_rows_after_a_clean_unit_are_measured(monkeypatch):
    # Rows filled while the pop-up was hidden kept it header-high.
    view = _make_view()
    view.btn_checks.set_active(True)
    _update(view, {'xmltags': 'Different XML tags'})
    view.update({})
    resized = []
    monkeypatch.setattr(view.tvw_checks, 'queue_resize', lambda: resized.append(True))

    _update(view, {'printf': 'Different printf variables'})

    assert resized == [True]


def test_the_button_has_no_tooltip_repeating_its_label():
    view = _make_view()

    _update(view, {'xmltags': 'Different XML tags'})

    assert view.btn_checks.get_tooltip_text() is None


def _geometry(view, button_y, natural_height, top):
    view._top_limit = lambda: top
    view._unscrolled_height = lambda height: height
    return view.update_geometry(None, None, None, SimpleNamespace(x=0, y=button_y), (0, 0, 100, natural_height))


def test_the_popup_keeps_its_height_when_it_fits_above_the_button():
    view = _make_view()

    assert _geometry(view, button_y=500, natural_height=200, top=100)[3] == 200


def test_the_popup_is_no_taller_than_the_room_above_the_button():
    # The screen clipped its top off on macOS (#4170); the list scrolls instead.
    view = _make_view()

    assert _geometry(view, button_y=250, natural_height=200, top=100)[3] == 150
    assert _geometry(view, button_y=120, natural_height=200, top=100)[3] == view.MIN_HEIGHT


def test_the_list_scrolls_only_while_the_popup_is_capped():
    # A scrollbar's minimum length made a one-row pop-up taller than its row.
    view = _make_view()

    _geometry(view, button_y=250, natural_height=200, top=100)
    assert view._scrolled.get_policy()[1] == Gtk.PolicyType.AUTOMATIC

    _geometry(view, button_y=500, natural_height=200, top=100)
    assert view._scrolled.get_policy()[1] == Gtk.PolicyType.NEVER


def test_the_scrollbar_doesnt_count_towards_the_popups_height():
    # Its minimum length kept a one-row pop-up capped, with a gap below (#4170).
    view = _make_view()
    view._scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    _update(view, {'printf': 'Missing printf variable: %s'})
    scrolled = view._scrolled.get_preferred_height()[1]
    tree = view.tvw_checks.get_preferred_height()[1]

    assert view._unscrolled_height(100) == 100 - scrolled + tree


def test_a_scrolling_popup_shows_only_whole_rows():
    view = _make_view()
    _update(view, {'check%d' % i: 'Description %d' % i for i in range(6)})
    view._top_limit = lambda: 0
    tree = view.tvw_checks.get_preferred_height()[1]
    header = view.tvw_checks.get_column(0).get_button().get_preferred_height()[1]
    row = (tree - header) / 6
    natural = tree + 10

    height = view.update_geometry(None, None, None, SimpleNamespace(x=0, y=int(natural - row * 2.5)),
                                  (0, 0, 100, natural))[3]

    assert height == int(natural - row * 3)
