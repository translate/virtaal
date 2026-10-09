#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
from types import SimpleNamespace

import pytest
from gi.repository import Gtk

from virtaal.support import statsdb
from virtaal.views import baseview
from virtaal.views.propertiesview import PropertiesView, _nice_percentage, _statistics


@pytest.fixture(autouse=True)
def _fresh_builder_cache(monkeypatch):
    # PropertiesView._get_widgets() loads real widgets from virtaal.ui -
    # a cached builder would hand back objects already used/mutated by
    # a previous test.
    monkeypatch.setattr(baseview, '_builders', {})


@pytest.fixture(autouse=True)
def _english_ui(monkeypatch):
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app, 'ui_language', 'en')


def test_statistics_logs_warning_when_state_dict_out_of_sync(monkeypatch, caplog):
    """_statistics()'s consistency check between descriptions and
    statsdb.extended_state_strings used an undefined `logging` name -
    raised NameError instead of the intended warning whenever the two
    tables disagree."""
    monkeypatch.setattr(statsdb, 'extended_state_strings', {0: 'unknown-state'})

    with caplog.at_level(logging.WARNING):
        result = _statistics({})

    assert any("doesn't correspond" in r.message for r in caplog.records)
    assert result == []


def test_statistics_orders_by_state_and_skips_absent_keys():
    stats = {
        'final': {'units': 5, 'sourcewords': 50},
        'empty': {'units': 2, 'sourcewords': 20},
    }

    result = _statistics(stats)

    assert result == [
        ('Untranslated:', 2, 20),
        ('Reviewed:', 5, 50),
    ]


def test_statistics_counts_requested_states_absent_from_stats_as_zero():
    stats = {'final': {'units': 5, 'sourcewords': 50}}

    result = _statistics(stats, {'empty', 'final'})

    assert result == [
        ('Untranslated:', 0, 0),
        ('Reviewed:', 5, 50),
    ]


# _nice_percentage() #

def test_nice_percentage_zero_numerator():
    assert _nice_percentage(0, 100) == '(0%)'


def test_nice_percentage_full():
    assert _nice_percentage(50, 50) == '(100%)'


def test_nice_percentage_single_digit_percentage():
    assert _nice_percentage(5, 100) == '(5.0%)'


def test_nice_percentage_general_case():
    assert _nice_percentage(25, 100) == '(25.0%)'


def test_nice_percentage_uses_the_ui_languages_format(monkeypatch):
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app, 'ui_language', 'de')

    assert _nice_percentage(1, 8) == '(12,5\xa0%)'


# PropertiesView construction #

def _real_builder():
    builder = Gtk.Builder()
    builder.add_from_file('share/virtaal/virtaal.ui')
    return builder


def _fake_controller(builder=None, store=None):
    builder = builder or _real_builder()
    main_window = Gtk.Window()
    mainview = SimpleNamespace(gui=builder, main_window=main_window, add_accel_group=lambda ag: None)
    main_controller = SimpleNamespace(
        view=mainview,
        store_controller=SimpleNamespace(get_store=lambda: store),
    )
    controller = SimpleNamespace(main_controller=main_controller, update_gui_data=lambda: None,
                                 save_file=lambda: True)
    return controller


def test_init_sets_up_empty_state():
    view = PropertiesView(_fake_controller())

    assert view._widgets == {}
    assert view.data == {}


def test_init_wires_the_menu_item_to_show():
    controller = _fake_controller()
    view = PropertiesView(controller)
    calls = []
    view.show = lambda: calls.append(True)

    controller.main_controller.view.gui.get_object('mnu_properties').activate()

    assert calls == [True]


def test_init_creates_an_accel_group_when_the_menu_has_none():
    controller = _fake_controller()
    menu_file = controller.main_controller.view.gui.get_object('menu_file')
    assert menu_file.get_accel_group() is None
    added = []
    controller.main_controller.view.add_accel_group = added.append

    PropertiesView(controller)

    assert menu_file.get_accel_group() is not None
    assert added == [menu_file.get_accel_group()]


def test_init_reuses_an_existing_accel_group():
    controller = _fake_controller()
    menu_file = controller.main_controller.view.gui.get_object('menu_file')
    existing = Gtk.AccelGroup()
    menu_file.set_accel_group(existing)
    added = []
    controller.main_controller.view.add_accel_group = added.append

    PropertiesView(controller)

    assert menu_file.get_accel_group() is existing
    assert added == []


def test_get_widgets_loads_every_named_widget_and_configures_the_dialog():
    controller = _fake_controller()
    view = PropertiesView(controller)

    view._get_widgets()

    for name in ('tbl_properties', 'lbl_type', 'lbl_location', 'lbl_filesize',
                 'lbl_word_total', 'lbl_string_total',
                 'vbox_word_labels', 'vbox_word_stats', 'vbox_word_perc',
                 'vbox_string_labels', 'vbox_string_stats', 'vbox_string_perc',
                 'lbl_saved_heading', 'lbl_live_heading',
                 'lbl_word_live_total', 'lbl_string_live_total',
                 'vbox_word_live_stats', 'vbox_string_live_stats',
                 'dialog', 'infobar'):
        assert view._widgets[name] is not None
    assert view._widgets['dialog'].get_transient_for() is controller.main_controller.view.main_window


# show() #

def _show_ready_view(**controller_kwargs):
    controller = _fake_controller(**controller_kwargs)
    view = PropertiesView(controller)
    view._init_gui()
    view.stats = {}
    view.data = {'file_type': 'PO'}
    view._widgets['dialog'].run = lambda: Gtk.ResponseType.CLOSE
    return view


def test_show_initializes_the_gui_on_first_call(monkeypatch):
    monkeypatch.setattr(Gtk.Dialog, 'run', lambda self: Gtk.ResponseType.CLOSE)
    view = PropertiesView(_fake_controller())
    view.stats = {}
    view.data = {'file_type': 'PO'}
    assert view._widgets == {}

    view.show()

    assert view._widgets  # _init_gui() ran because _widgets started empty


def test_show_calls_update_gui_data():
    view = _show_ready_view()
    calls = []
    view.controller.update_gui_data = lambda: calls.append(True)

    view.show()

    assert calls == [True]


_LIVE_ONLY_WIDGETS = ('infobar', 'lbl_saved_heading', 'lbl_live_heading',
                      'lbl_word_live_total', 'lbl_string_live_total',
                      'vbox_word_live_stats', 'vbox_string_live_stats')


def test_show_hides_the_unsaved_changes_widgets_for_an_unmodified_file():
    view = _show_ready_view()

    view.show()

    for name in _LIVE_ONLY_WIDGETS:
        assert not view._widgets[name].get_visible(), name


def test_show_shows_the_unsaved_changes_widgets_for_a_modified_file():
    view = _show_ready_view()
    view.live_stats = {}

    view.show()

    for name in _LIVE_ONLY_WIDGETS:
        assert view._widgets[name].get_visible(), name


def test_show_puts_the_infobar_above_the_notebook():
    view = _show_ready_view()

    children = view._widgets['dialog'].get_content_area().get_children()

    assert children.index(view._widgets['infobar']) < children.index(view.gui.get_object('notebook2'))


def _modified_view():
    view = _show_ready_view()
    view.stats = {
        'empty': {'units': 2, 'sourcewords': 20},
        'final': {'units': 8, 'sourcewords': 80},
    }
    # One unit of 10 words reviewed since the last save.
    view.live_stats = {
        'empty': {'units': 1, 'sourcewords': 10},
        'final': {'units': 9, 'sourcewords': 90},
    }
    return view


def test_show_fills_the_unsaved_changes_column():
    view = _modified_view()

    view.show()

    word_stats = [c.get_text() for c in view._widgets['vbox_word_live_stats'].get_children()]
    assert word_stats == ['10  (10.0%)', '90  (90.0%)']
    string_stats = [c.get_text() for c in view._widgets['vbox_string_live_stats'].get_children()]
    assert string_stats == ['1  (10.0%)', '9  (90.0%)']
    assert view._widgets['lbl_word_live_total'].get_label() == '<b>100</b>'
    assert view._widgets['lbl_string_live_total'].get_label() == '<b>10</b>'


def test_show_marks_unsaved_values_that_differ_from_the_saved_file():
    view = _modified_view()
    view.live_stats['final']['units'] = 8  # unchanged from the saved file

    view.show()

    string_markup = [c.get_label() for c in view._widgets['vbox_string_live_stats'].get_children()]
    assert string_markup[0].startswith('<b>')
    assert not string_markup[1].startswith('<b>')


def test_show_lists_a_state_present_in_only_one_column_in_both():
    view = _show_ready_view()
    view.stats = {'empty': {'units': 1, 'sourcewords': 5}}
    view.live_stats = {'final': {'units': 1, 'sourcewords': 5}}

    view.show()

    labels = [c.get_label() for c in view._widgets['vbox_word_labels'].get_children()]
    assert labels == ['Untranslated:', 'Reviewed:']
    saved = [c.get_label() for c in view._widgets['vbox_word_stats'].get_children()]
    assert saved == ['5  (100%)', '0  (0%)']
    live = [c.get_text() for c in view._widgets['vbox_word_live_stats'].get_children()]
    assert live == ['0  (0%)', '5  (100%)']


def test_infobar_save_refreshes_the_dialog_after_a_successful_save():
    view = _modified_view()
    view.show()

    def update_gui_data():
        view.stats, view.live_stats = view.live_stats, None
    view.controller.update_gui_data = update_gui_data
    view._widgets['infobar'].response(Gtk.ResponseType.ACCEPT)

    assert not view._widgets['infobar'].get_visible()
    saved = [c.get_label() for c in view._widgets['vbox_word_stats'].get_children()]
    assert saved == ['10  (10.0%)', '90  (90.0%)']


def test_show_shrinks_the_dialog_to_fit_its_content(monkeypatch):
    view = _show_ready_view()
    sizes = []
    monkeypatch.setattr(view._widgets['dialog'], 'resize', lambda w, h: sizes.append((w, h)))

    view.show()

    assert sizes == [(1, 1)]


def test_infobar_save_leaves_the_dialog_alone_when_the_save_fails():
    view = _modified_view()
    view.show()
    refreshed = []
    view.controller.update_gui_data = lambda: refreshed.append(True)
    view.controller.save_file = lambda: False

    view._widgets['infobar'].response(Gtk.ResponseType.ACCEPT)

    assert refreshed == []
    assert view._widgets['infobar'].get_visible()


def test_show_populates_stats_labels_in_state_order():
    # _statistics() returns (description, units, sourcewords) -
    # show()'s own local names swap them: "words" is sourcewords,
    # "strings" is units.
    view = _show_ready_view()
    view.stats = {
        'empty': {'units': 2, 'sourcewords': 20},
        'final': {'units': 8, 'sourcewords': 80},
    }

    view.show()

    word_labels = [c.get_label() for c in view._widgets['vbox_word_labels'].get_children()]
    assert word_labels == ['Untranslated:', 'Reviewed:']
    word_stats = [c.get_label() for c in view._widgets['vbox_word_stats'].get_children()]
    assert word_stats == ['20  (20.0%)', '80  (80.0%)']
    string_stats = [c.get_label() for c in view._widgets['vbox_string_stats'].get_children()]
    assert string_stats == ['2  (20.0%)', '8  (80.0%)']


def test_show_uses_the_ui_languages_number_format(monkeypatch):
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app, 'ui_language', 'fa')
    view = _show_ready_view()
    view.stats = {
        'empty': {'units': 2, 'sourcewords': 2000},
        'final': {'units': 8, 'sourcewords': 6000},
    }

    view.show()

    word_stats = [c.get_label() for c in view._widgets['vbox_word_stats'].get_children()]
    assert word_stats == ['۲٬۰۰۰  (۲۵٫۰%)', '۶٬۰۰۰  (۷۵٫۰%)']
    assert view._widgets['lbl_word_total'].get_label() == '<b>۸٬۰۰۰</b>'


def test_show_sets_the_word_and_string_totals():
    view = _show_ready_view()
    view.stats = {
        'empty': {'units': 2, 'sourcewords': 20},
        'final': {'units': 8, 'sourcewords': 80},
    }

    view.show()

    assert view._widgets['lbl_word_total'].get_label() == '<b>100</b>'
    assert view._widgets['lbl_string_total'].get_label() == '<b>10</b>'


def test_show_clears_labels_from_a_previous_call():
    view = _show_ready_view()
    view.stats = {'empty': {'units': 1, 'sourcewords': 1}}
    view.show()

    view.stats = {'final': {'units': 1, 'sourcewords': 1}}
    view.show()

    labels = [c.get_label() for c in view._widgets['vbox_word_labels'].get_children()]
    assert labels == ['Reviewed:']


def test_show_sets_file_type_and_location():
    view = _show_ready_view()
    view.data = {'file_type': 'PO', 'file_location': '/tmp/x.po'}

    view.show()

    assert view._widgets['lbl_type'].get_text() == 'PO'
    assert view._widgets['lbl_location'].get_text() == '/tmp/x.po'
    assert view._widgets['lbl_location'].get_tooltip_text() == '/tmp/x.po'


def test_show_translates_the_file_type(monkeypatch):
    import builtins
    real = builtins._
    monkeypatch.setattr(builtins, '_', lambda s: 'Gettext PO-lêer' if s == 'Gettext PO file' else real(s))
    view = _show_ready_view()
    view.data = {'file_type': 'Gettext PO file'}

    view.show()

    assert view._widgets['lbl_type'].get_text() == 'Gettext PO-lêer'


def test_show_leaves_location_tooltip_unset_without_a_location():
    view = _show_ready_view()
    view.data = {'file_type': 'PO'}

    view.show()

    assert view._widgets['lbl_location'].get_text() == ''


def test_show_sets_file_size_when_present():
    view = _show_ready_view()
    view.data = {'file_type': 'PO', 'file_size': 2048}

    view.show()

    assert '2.0' in view._widgets['lbl_filesize'].get_text()


def test_show_gives_a_large_file_size_in_a_larger_unit():
    view = _show_ready_view()
    view.data = {'file_type': 'PO', 'file_size': 5_242_880}

    view.show()

    assert view._widgets['lbl_filesize'].get_text() == '5.2 MB'


def test_show_gives_the_file_size_in_the_ui_languages_digits(monkeypatch):
    from virtaal.common import pan_app
    monkeypatch.setattr(pan_app, 'ui_language', 'ne')
    view = _show_ready_view()
    view.data = {'file_type': 'PO', 'file_size': 18_700}

    view.show()

    assert view._widgets['lbl_filesize'].get_text() == '१८.७ kB'


def test_show_leaves_file_size_untouched_when_absent():
    view = _show_ready_view()
    view.data = {'file_type': 'PO'}
    view.show()
    view._widgets['lbl_filesize'].set_text('previous')

    view.show()

    assert view._widgets['lbl_filesize'].get_text() == 'previous'


def test_show_presents_the_transient_parent_again_after_closing(monkeypatch):
    calls = []
    monkeypatch.setattr('virtaal.views.propertiesview.GLib.idle_add', lambda func, *a: calls.append((func, a)))
    view = _show_ready_view()

    view.show()

    assert len(calls) == 1
    func, _args = calls[0]
    assert func == view._widgets['dialog'].get_transient_for().present
