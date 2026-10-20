#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.common import pan_app
from virtaal.controllers.baseplugin import BasePlugin

from .tmcontroller import TMController


class Plugin(BasePlugin):
    display_name = _('Translation Memory')
    description = _('Translation memory suggestions')
    version = 0.1
    default_config = {
        'disabled_models': '_dummytm,remotetm,apertium,google_translate,moses',
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
        self.config['disabled_models'] = self.config['disabled_models'].split(',')
        self.config['max_matches'] = pan_app.config_int(
            self.config['max_matches'], int(self.default_config['max_matches']), 0, 1000, 'max_matches')
        # A quality of 0 divides by zero when matching.
        self.config['min_quality'] = pan_app.config_int(
            self.config['min_quality'], int(self.default_config['min_quality']), 1, 100, 'min_quality')

        self.controller = TMController(self.main_controller, self.config)
