#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import GObject

from virtaal.common import SignalTracker
from virtaal.common.configurable import Configurable
from virtaal.models.basemodel import BaseModel


class BaseTerminologyModel(BaseModel, Configurable):
    """The base interface to be implemented by all terminology backend models."""

    __gtype_name__ = None
    __gsignals__ = {
        'match-found': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_STRING, GObject.TYPE_PYOBJECT,))
    }

    CONFIG_FILENAME = "terminology.ini"

    configure_func = None
    """A function that starts the configuration, if available."""
    display_name = None
    """The backend's name, suitable for display."""

    # INITIALIZERS #
    def __init__(self, controller):
        """Initialise the model and connects it to the appropriate events.

            Only call this from child classes once the object was successfully
            created and want to be connected to signals."""
        super().__init__()
        self.config = {}
        self.controller = controller
        self._signal_tracker = SignalTracker()

        #static suggestion cache for slow terminology queries
        #TODO: cache invalidation, maybe decorate query to automate cache handling?
        self.cache = {}


    # METHODS #
    def destroy(self):
        self.save_config()
        self._signal_tracker.disconnect_all()
