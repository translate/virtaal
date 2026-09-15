#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os.path

from gi.repository import GObject
from translate.storage.placeables import parse as elem_parse
from translate.storage.placeables import terminology

from virtaal.common import GObjectWrapper
from virtaal.controllers.basecontroller import BaseController
from virtaal.controllers.plugincontroller import PluginController
from virtaal.views import placeablesguiinfo

from .models.basetermmodel import BaseTerminologyModel
from .termview import TerminologyGUIInfo, TerminologyView


class TerminologyController(BaseController):
    """The logic-filled glue between the terminology view and -model."""

    __gtype_name__ = 'TerminologyController'
    __gsignals__ = {
        'start-query': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_STRING,))
    }

    # INITIALIZERS #
    def __init__(self, main_controller, config={}):
        GObjectWrapper.__init__(self)

        self.config = config
        self.main_controller = main_controller
        self.placeables_controller = main_controller.placeables_controller

        self.disabled_model_names = ['basetermmodel'] + self.config.get('disabled_models', [])
        self.placeables_controller.add_parsers(*terminology.parsers)
        self.placeables_controller.non_target_placeables.append(terminology.TerminologyPlaceable)
        self.placeables_controller.connect('parsers-changed', self._on_placeables_changed)
        main_controller.view.main_window.connect('style-set', self._on_style_set)
        main_controller.view.main_window.connect('style-updated', self._on_style_set)
        self._on_style_set(main_controller.view.main_window, None)

        if not (terminology.TerminologyPlaceable, TerminologyGUIInfo) in placeablesguiinfo.element_gui_map:
            placeablesguiinfo.element_gui_map.insert(0, (terminology.TerminologyPlaceable, TerminologyGUIInfo))

        self.view = TerminologyView(self)
        self._connect_signals()
        self._load_models()

    def _connect_signals(self):
        lang_controller = self.main_controller.lang_controller
        lang_controller.connect('source-lang-changed', lambda *args: self.rescan_current_unit())
        lang_controller.connect('target-lang-changed', lambda *args: self.rescan_current_unit())

    def _load_models(self):
        self.plugin_controller = PluginController(self, 'TerminologyModel')
        self.plugin_controller.PLUGIN_CLASS_INFO_ATTRIBS = ['description', 'display_name']
        new_dirs = []
        for dir in self.plugin_controller.PLUGIN_DIRS:
           new_dirs.append(os.path.join(dir, 'terminology', 'models'))
        self.plugin_controller.PLUGIN_DIRS = new_dirs

        self.plugin_controller.PLUGIN_INTERFACE = BaseTerminologyModel
        self.plugin_controller.PLUGIN_MODULES = ['virtaal_plugins.terminology.models', 'virtaal.plugins.terminology.models']
        self.plugin_controller.get_disabled_plugins = lambda *args: self.disabled_model_names
        self.plugin_controller.connect('plugin-enabled', lambda *args: self.rescan_current_unit())
        self.plugin_controller.load_plugins()


    # METHODS #
    def destroy(self):
        self.view.destroy()
        self.plugin_controller.shutdown()
        self.placeables_controller.remove_parsers(terminology.parsers)

    def rescan_current_unit(self):
        """Force the current unit's terminology to be re-scanned (#3240).

        remove_type() alone only strips stale matches - refresh() re-renders
        the tree but never re-runs the placeable parsers, so parse() is what
        actually re-detects current ones."""
        unit_controller = getattr(self.main_controller, 'unit_controller', None)
        if unit_controller is None:
            return
        for src in unit_controller.view.sources:
            src.elem.remove_type(terminology.TerminologyPlaceable)
            elem_parse(src.elem, terminology.parsers)
            src.refresh(update=True)


    # EVENT HANDLERS #
    def _on_placeables_changed(self, placeables_controller):
        for term_parser in terminology.parsers:
            if term_parser not in placeables_controller.parsers:
                placeables_controller.add_parsers(term_parser)

    def _on_style_set(self, widget, prev_style=None):
        TerminologyGUIInfo.update_style(widget)
