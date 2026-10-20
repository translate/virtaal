#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.common import pan_app
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
        self.config['backends_dialog_width'] = pan_app.config_int(
            self.config['backends_dialog_width'], self.default_config['backends_dialog_width'], 1, 32767,
            'backends_dialog_width')
        self.config['disabled_models'] = self.config['disabled_models'].split(',')
        # A profile saved before autoterm's own default disabling (see
        # default_config above) keeps whatever disabled_models it last
        # saved, silently re-enabling a plugin whose one URL has been
        # dead for years - this isn't a user preference to honour, so
        # enforce it regardless of what an old config says.
        if 'autoterm' not in self.config['disabled_models']:
            self.config['disabled_models'].append('autoterm')
        self.config['max_matches'] = pan_app.config_int(
            self.config['max_matches'], int(self.default_config['max_matches']), 0, 1000, 'max_matches')
        # A quality of 0 divides by zero when matching.
        self.config['min_quality'] = pan_app.config_int(
            self.config['min_quality'], int(self.default_config['min_quality']), 1, 100, 'min_quality')

        self.controller = TerminologyController(self.main_controller, self.config)
