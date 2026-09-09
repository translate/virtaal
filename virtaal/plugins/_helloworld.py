#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""example plugin."""

import logging

from virtaal.controllers.baseplugin import BasePlugin


class Plugin(BasePlugin):
    description = _('Simple plug-in that serves as an example to developers.')
    display_name = _('Hello World')
    version = '0.1'
    default_config = {
        "name": "Hello World",
        "question": "Stop annoying you?",
        "info": "Store loaded!"
    }

    # INITIALIZERS #
    def __init__(self, internal_name, main_controller):
        self.internal_name = internal_name
        self.main_controller = main_controller

        self.load_config()
        self._init_plugin()
        logging.debug('HelloWorld loaded')

        self.annoy = True

    def _init_plugin(self):
        self._store_loaded_id = self.main_controller.store_controller.connect('store-loaded', self.on_store_loaded)

        if self.main_controller.store_controller.get_store():
            self.on_store_loaded(self.main_controller.store_controller)


    # METHODS #
    def destroy(self):
        self.main_controller.store_controller.disconnect(self._store_loaded_id)
        if getattr(self, '_cursor_changed_id', None):
            self.main_controller.store_controller.cursor.disconnect(self._cursor_changed_id)
        self.save_config()


    # EVENT HANDLERS #
    def on_store_loaded(self, storecontroller):
        self.main_controller.show_info(self.config["name"], self.config["info"])
        self._cursor_changed_id = storecontroller.cursor.connect('cursor-changed', self.on_cursor_change)

    def on_cursor_change(self, cursor):
        if self.annoy:
            self.annoy = not self.main_controller.show_prompt(self.config["name"], self.config["question"])
