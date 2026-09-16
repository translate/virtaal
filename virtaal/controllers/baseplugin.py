#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.common.configurable import Configurable


class PluginUnsupported(Exception):
    pass

class BasePlugin(Configurable):
    """The base interface to be implemented by all plug-ins."""

    CONFIG_FILENAME = "plugins.ini"

    configure_func = None
    """A function that starts the plug-in's configuration, if available."""
    description = ''
    """A description about the plug-in's purpose."""
    display_name = ''
    """The plug-in's name, suitable for display."""
    version = '0'
    """The plug-in's version number."""

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
