#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.controllers.baseplugin import BasePlugin
from .termcontroller import TerminologyController


class Plugin(BasePlugin):
    display_name = _('Terminology Help')
    description = _('Terminology suggestions')
    version = 0.1
    default_config = {
        'backends_dialog_width': 400,
        # autoterm's default URL (terminology.locamotion.org) is dead -
        # disabled until it has somewhere working to point at. The
        # plugin itself (fetch-any-URL terminology) stays, since it's a
        # distinct concept from Pontoon's own fixed, specific source.
        'disabled_models': 'autoterm',
        'max_matches': '5',
        'min_quality': '70'
    }

    # INITIALIZERS #
    def __init__(self, internal_name, main_controller):
        self.configure_func = self.configure
        self.internal_name = internal_name
        self.main_controller = main_controller
        self._init_plugin()

    def _init_plugin(self):
        self.load_config()
        self.config['backends_dialog_width'] = int(self.config['backends_dialog_width'])
        self.config['disabled_models'] = self.config['disabled_models'].split(',')
        self.config['max_matches'] = int(self.config['max_matches'])
        self.config['min_quality'] = int(self.config['min_quality'])

        self.termcontroller = TerminologyController(self.main_controller, self.config)

    def configure(self, parent):
        self.termcontroller.view.select_backends(parent)

    def destroy(self):
        self.config = self.termcontroller.config
        self.save_config()
        self.termcontroller.destroy()
