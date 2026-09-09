#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

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
        self.config['max_matches'] = int(self.config['max_matches'])
        self.config['min_quality'] = int(self.config['min_quality'])

        self.tmcontroller = TMController(self.main_controller, self.config)


    # METHODS #
    def configure(self, parent):
        self.tmcontroller.view.select_backends(parent)

    def destroy(self):
        self.config = self.tmcontroller.config
        self.save_config()
        self.tmcontroller.destroy()
