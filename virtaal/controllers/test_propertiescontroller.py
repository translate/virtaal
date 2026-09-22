#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from virtaal.controllers.propertiescontroller import PropertiesController


def _controller(store):
    controller = PropertiesController.__new__(PropertiesController)
    controller.view = SimpleNamespace(data={})
    controller.main_controller = SimpleNamespace(
        store_controller=SimpleNamespace(get_store=lambda: store)
    )
    return controller


def test_update_gui_data_sets_file_info_when_the_file_exists(tmp_path):
    real_file = tmp_path / "file.po"
    real_file.write_text("data")
    store = SimpleNamespace(
        get_filename=lambda: str(real_file),
        get_store_type=lambda: 'po',
        get_stats_totals=lambda: {'total': 3},
    )
    controller = _controller(store)

    controller.update_gui_data()

    assert controller.view.data['file_location'] == str(real_file)
    assert controller.view.data['file_size'] == real_file.stat().st_size
    assert controller.view.data['file_type'] == 'po'
    assert controller.view.stats == {'total': 3}


def test_update_gui_data_skips_file_info_for_a_missing_file(tmp_path):
    store = SimpleNamespace(
        get_filename=lambda: str(tmp_path / "does-not-exist.po"),
        get_store_type=lambda: 'po',
        get_stats_totals=lambda: {'total': 0},
    )
    controller = _controller(store)

    controller.update_gui_data()

    assert 'file_location' not in controller.view.data
    assert 'file_size' not in controller.view.data
    assert controller.view.data['file_type'] == 'po'
    assert controller.view.stats == {'total': 0}
