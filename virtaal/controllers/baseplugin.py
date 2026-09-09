#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os

from virtaal.common import pan_app


class PluginUnsupported(Exception):
    pass

class BasePlugin:
    """The base interface to be implemented by all plug-ins."""

    configure_func = None
    """A function that starts the plug-in's configuration, if available."""
    description = ''
    """A description about the plug-in's purpose."""
    display_name = ''
    """The plug-in's name, suitable for display."""
    version = '0'
    """The plug-in's version number."""
    default_config = {}

    # INITIALIZERS #
    def __new__(cls, *args, **kwargs):
        """Create a new plug-in instance and check that it is valid."""
        if not cls.display_name:
            raise Exception('No name specified')
        if str(cls.version) <= '0':
            raise Exception('Invalid version number specified')
        return super().__new__(cls)

    def __init__(self):
        raise NotImplementedError('This interface cannot be instantiated.')

    # METHODS #
    def destroy(self):
        """This method is called by C{PluginController.shutdown()} and should be
            implemented by all plug-ins that need to do clean-up."""
        pass

    def load_config(self):
        """Load plugin config from default location."""
        self.config = {}
        self.config.update(self.default_config)
        config_file = os.path.join(pan_app.get_config_dir(), "plugins.ini")
        self.config.update(pan_app.load_config(config_file, self.internal_name))

    def save_config(self):
        """Save plugin config to default location."""
        config_file = os.path.join(pan_app.get_config_dir(), "plugins.ini")
        pan_app.save_config(config_file, self.config, self.internal_name)
