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
