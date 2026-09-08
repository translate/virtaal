#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Performs external look-ups on selected text."""

from virtaal.controllers.baseplugin import BasePlugin
from .lookupcontroller import LookupController


class Plugin(BasePlugin):
    description = _('Perform look-ups on selected text')
    display_name = _('External Look-up')
    version = '0.1'

    default_config = {
        'backends_dialog_width': 450,
        'disabled_models': '',
    }

    # INITIALIZERS #
    def __init__(self, internal_name, main_controller):
        self.configure_func = self.configure
        self.internal_name = internal_name
        self.main_controller = main_controller

        self.load_config()
        self.config['disabled_models'] = self.config['disabled_models'].split(',')
        self.config['backends_dialog_width'] = int(self.config['backends_dialog_width'])
        self._init_plugin()

    def _init_plugin(self):
        self.controller = LookupController(self, self.config)


    # METHODS #
    def configure(self, parent):
        self.controller.view.select_backends(parent)

    def destroy(self):
        self.config = self.controller.config
        self.save_config()
        self.controller.destroy()
