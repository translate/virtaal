#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os

from gi.repository import GObject

from virtaal.common import pan_app
from virtaal.models.basemodel import BaseModel


class BaseTerminologyModel(BaseModel):
    """The base interface to be implemented by all terminology backend models."""

    __gtype_name__ = None
    __gsignals__ = {
        'match-found': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_STRING, GObject.TYPE_PYOBJECT,))
    }

    configure_func = None
    """A function that starts the configuration, if available."""
    display_name = None
    """The backend's name, suitable for display."""
    default_config = {}
    """Default configuration shared by all terminology model plug-ins."""

    # INITIALIZERS #
    def __init__(self, controller):
        """Initialise the model and connects it to the appropriate events.

            Only call this from child classes once the object was successfully
            created and want to be connected to signals."""
        super().__init__()
        self.config = {}
        self.controller = controller
        self._connect_ids = []

        #static suggestion cache for slow terminology queries
        #TODO: cache invalidation, maybe decorate query to automate cache handling?
        self.cache = {}


    # METHODS #
    def destroy(self):
        self.save_config()
        #disconnect all signals
        [widget.disconnect(cid) for (cid, widget) in self._connect_ids]

    def load_config(self):
        """Load terminology backend config from default location"""
        self.config = {}
        self.config.update(self.default_config)
        config_file = os.path.join(pan_app.get_config_dir(), "terminology.ini")
        self.config.update(pan_app.load_config(config_file, self.internal_name))

    def save_config(self):
        """Save terminology backend config to default location"""
        config_file = os.path.join(pan_app.get_config_dir(), "terminology.ini")
        pan_app.save_config(config_file, self.config, self.internal_name)
