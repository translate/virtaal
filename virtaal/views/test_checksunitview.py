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
    return [(name.get_text(), desc.get_text()) for name, desc in view.check_rows]


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


def test_the_unseen_button_is_named_and_out_of_the_focus_chain():
    view = _make_view()
    _update(view, {'xmltags': 'Different XML tags'})
    _update(view, {})

    assert not view.btn_checks.get_can_focus()
    assert view.btn_checks.get_accessible().get_name() == 'Quality checks'

    _update(view, {'xmltags': 'Different XML tags', 'urls': 'Different URLs'})

    assert view.btn_checks.get_can_focus()
    assert view.btn_checks.get_accessible().get_name() == view.lbl_btnchecks.get_text()


def test_pressing_the_button_before_any_failures_pops_up_nothing():
    view = _make_view()

    view.btn_checks.set_active(True)

    assert not view.btn_checks.is_popup_visible


def test_untranslated_alone_counts_as_no_failures():
    view = _make_view()
    view.btn_checks.set_active(True)

    _update(view, {'untranslated': 'Untranslated'})

    assert not view.btn_checks.is_popup_visible


def test_new_rows_after_a_clean_unit_are_measured():
    # Rows filled while the pop-up was hidden kept it header-high.
    view = _make_view()
    view.btn_checks.set_active(True)
    _update(view, {'xmltags': 'Different XML tags'})
    one_row = view.btn_checks.popup.get_preferred_size()[1].height
    view.update({})

    _update(view, {'printf': 'Different printf variables', 'xmltags': 'Different XML tags'})

    assert _rows(view) == [('printf', 'Different printf variables'), ('xmltags', 'Different XML tags')]
    assert view.btn_checks.popup.get_preferred_size()[1].height > one_row


def _place(view):
    view._top_limit = lambda: 0
    natural = view.btn_checks.popup.get_child().get_preferred_size()[1]
    return view.update_geometry(view.btn_checks.popup, None, None, SimpleNamespace(x=0, y=10000),
                                (0, 0, natural.width, natural.height))


def test_long_descriptions_wrap_to_the_maximum_width():
    view = _make_view()
    view.btn_checks.set_active(True)
    _update(view, {'xmltags': 'Different XML tags'})
    one_line = view.btn_checks.popup.get_preferred_size()[1].height
    view.controller.main_controller.unit_controller.view.sources[0] = SimpleNamespace(
        get_allocation=lambda: SimpleNamespace(width=400))

    _update(view, {'xmltags': 'Different XML tags ' * 20})
    x, y, width, height = _place(view)

    assert 400 < width <= 520
    assert height > one_line


def test_placing_wrapped_descriptions_again_changes_nothing():
    # Each change to the pop-up's size places it again.
    view = _make_view()
    view.btn_checks.set_active(True)
    view.controller.main_controller.unit_controller.view.sources[0] = SimpleNamespace(
        get_allocation=lambda: SimpleNamespace(width=400))
    _update(view, {'xmltags': 'Different XML tags ' * 20})
    _place(view)
    placed = _place(view)

    assert _place(view) == placed
    natural = view.btn_checks.popup.get_child().get_preferred_size()[1]
    assert placed[2:] == (natural.width, natural.height)


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
    rows = view.box_checks.get_preferred_height()[1]

    assert view._unscrolled_height(100) == 100 - scrolled + rows


def test_a_scrolling_popup_shows_only_whole_rows():
    view = _make_view()
    _update(view, {'check%d' % i: 'Description %d' % i for i in range(6)})
    view.controller.main_controller.unit_controller.view.sources[0] = SimpleNamespace(
        get_allocation=lambda: SimpleNamespace(width=400))
    view._top_limit = lambda: 0
    view._unscrolled_height = lambda height: height
    row = view.box_checks.get_children()[0].get_preferred_height()[1]
    spacing = view.box_checks.get_spacing()
    natural = view.box_checks.get_preferred_height()[1] + 10

    height = view.update_geometry(None, None, None, SimpleNamespace(x=0, y=int(natural - (row + spacing) * 2.5)),
                                  (0, 0, 100, natural))[3]

    assert height == 10 + 3 * row + 2 * spacing
