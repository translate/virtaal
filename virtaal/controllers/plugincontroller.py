#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import logging
import os
import sys

from virtaal.common import pan_app, GObjectWrapper

from basecontroller import BaseController
from baseplugin import BasePlugin


if os.name == 'nt':
    sys.path.insert(0, pan_app.main_dir)

# The following line allows us to import user plug-ins from ~/.virtaal/virtaal_plugins
# (see PluginController.PLUGIN_MODULES)
sys.path.insert(0, pan_app.get_config_dir())

class PluginController(BaseController):
    """This controller is responsible for all plug-in management."""

    __gtype_name__ = 'PluginController'

    DEBUG = False
    """If C{True}, allows exceptions during plug-in load to bubble up, in stead of being caught."""
    # The following class variables are set for the main plug-in controller.
    # To use this class to manage any other plug-ins, these will (most likely) have to be changed.
    PLUGIN_CLASSNAME = 'Plugin'
    """The name of the class that will be instantiated from the plug-in module."""
    PLUGIN_DIRS = [
        os.path.join(pan_app.get_config_dir(), 'virtaal_plugins'),
        os.path.join(os.path.dirname(__file__), '..', 'plugins')
    ]
    """The directories to search for plug-in names."""
    PLUGIN_INTERFACE = BasePlugin
    """The interface class that the plug-in class must inherit from."""
    PLUGIN_MODULES = ['virtaal_plugins', 'virtaal.plugins']
    """The module name to import the plugin from. This is prepended to the
        plug-in's name as found by C{_find_plugin_names()} and passed to
        C{__import__()}."""
    PLUGIN_NAME_ATTRIB = 'display_name'
    """The attribute of a plug-in that contains its name."""

    # INITIALIZERS #
    def __init__(self, controller):
        GObjectWrapper.__init__(self)

        self.controller = controller
        self.plugins       = {}
        self.pluginmodules = {}

        if os.name == 'nt':
            self.PLUGIN_DIRS.insert(0, os.path.join(pan_app.main_dir, 'virtaal_plugins'))


    # METHODS #
    def disable_plugin(self, name):
        """Destroy the plug-in with the given name."""
        if name in self.plugins:
            self.plugins[name].destroy()
            del self.plugins[name]
        if name in self.pluginmodules:
            del self.pluginmodules[name]

    def enable_plugin(self, name):
        """Load the plug-in with the given name and instantiate it."""
        logging.debug('Enabling plugin: %s' % (name))
        if name in self.plugins:
            return None

        try:
            if name not in self.pluginmodules:
                module = None
                for plugin_module in self.PLUGIN_MODULES:
                    # The following line makes sure that we have a valid module name to import from
                    modulename = '.'.join([part for part in [plugin_module, name] if part])
                    try:
                        logging.debug('from %s import %s' % (modulename, self.PLUGIN_CLASSNAME))
                        module = __import__(
                            modulename,
                            globals=globals(),
                            fromlist=[self.PLUGIN_CLASSNAME]
                        )
                        break
                    except ImportError, ie:
                        logging.debug('ImportError for %s: %s' % (modulename, ie))
                        pass

                if module is None:
                    raise Exception('Could not find plug-in "%s"' % (name))

                plugin_class = getattr(module, self.PLUGIN_CLASSNAME, None)
                if plugin_class is None:
                    raise Exception('Plugin "%s" has no class called "%s"' % (name, self.PLUGIN_CLASSNAME))

                if self.PLUGIN_INTERFACE is not None:
                    if not issubclass(plugin_class, self.PLUGIN_INTERFACE):
                        raise Exception(
                            'Plugin "%s" contains a member called "%s" which is not a valid plug-in class.' % (name, self.PLUGIN_CLASSNAME)
                        )

                self.pluginmodules[name] = module

            self.plugins[name] = plugin_class(name, self.controller)
            logging.info('    - ' + getattr(self.plugins[name], self.PLUGIN_NAME_ATTRIB, name))
            return self.plugins[name]
        except Exception, exc:
            logging.warning('Failed to load plugin "%s": %s' % (name, exc))
            if self.DEBUG:
                raise

        return None

    def load_plugins(self):
        """Load plugins from the "plugins" directory."""
        self.plugins       = {}
        self.pluginmodules = {}
        disabled_plugins = self.get_disabled_plugins()

        logging.info('Loading plug-ins:')
        for name in self._find_plugin_names():
            if name in disabled_plugins:
                continue
            self.enable_plugin(name)
        logging.info('Done loading plug-ins.')

    def shutdown(self):
        """Disable all plug-ins."""
        for name in list(self.plugins.keys()):
            self.disable_plugin(name)

    def _find_plugin_names(self):
        plugin_names = []

        for dir in self.PLUGIN_DIRS:
            if not os.path.isdir(dir):
                continue
            for name in os.listdir(dir):
                if name.startswith('.'):
                    continue
                fullpath = os.path.join(dir, name)
                if os.path.isdir(fullpath):
                    # XXX: The plug-in system assumes that a plug-in in a directory makes the Plugin class accessible via it's __init__.py
                    plugin_names.append(name)
                elif os.path.isfile(fullpath) and not name.startswith('__init__.py'):
                    plugname = '.'.join(name.split('.')[:-1]) # Effectively removes extension, preserving other .'s int he name
                    plugin_names.append(plugname)

        plugin_names = list(set(plugin_names))
        logging.debug('Found plugins: %s' % (plugin_names))
        return plugin_names

    def get_disabled_plugins(self):
        return [plugin_name for (plugin_name, state) in pan_app.settings.plugin_state.items() if state.lower() == 'disabled']
