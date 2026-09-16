#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging


def select_backends(main_controller, plugin_controller, config, base_model_name,
                     title, message, size, parent=None):
    """Build and run a SelectDialog listing plugin_controller's available
    backend models, wiring enable/disable through to plugin_controller and
    config['disabled_models'] - the terminology/TM/look-up views' own
    select_backends() otherwise reimplement this identically, differing
    only in these parameters."""
    from virtaal.views.widgets.selectdialog import SelectDialog

    selectdlg = SelectDialog(title=title, message=message, parent=parent, size=size)
    selectdlg.set_icon(main_controller.view.main_window.get_icon())

    items = []
    for plugin_name in plugin_controller._find_plugin_names():
        if plugin_name == base_model_name:
            continue
        try:
            info = plugin_controller.get_plugin_info(plugin_name)
        except Exception:
            logging.debug('Problem getting information for plugin %s' % plugin_name)
            continue
        enabled = plugin_name in plugin_controller.plugins
        backend_config = enabled and plugin_controller.plugins[plugin_name].configure_func or None
        items.append({
            'name': info['display_name'],
            'desc': info['description'],
            'data': {'internal_name': plugin_name},
            'enabled': enabled,
            'config': backend_config,
        })

    def item_enabled(dlg, item):
        internal_name = item['data']['internal_name']
        plugin_controller.enable_plugin(internal_name)
        if internal_name in config['disabled_models']:
            config['disabled_models'].remove(internal_name)

    def item_disabled(dlg, item):
        internal_name = item['data']['internal_name']
        plugin_controller.disable_plugin(internal_name)
        if internal_name not in config['disabled_models']:
            config['disabled_models'].append(internal_name)

    selectdlg.connect('item-enabled', item_enabled)
    selectdlg.connect('item-disabled', item_disabled)
    selectdlg.run(items=items)
