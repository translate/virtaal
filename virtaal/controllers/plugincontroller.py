#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2011 Zuza Software Foundation
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

from gi.repository import GLib, GObject
from gi.repository.GObject import TYPE_PYOBJECT

from virtaal.common import pan_app, GObjectWrapper
from virtaal.common.utils import get_unicode
from .basecontroller import BaseController
from .baseplugin import PluginUnsupported, BasePlugin

if os.name == 'nt':
    sys.path.insert(0, pan_app.main_dir)
if 'RESOURCEPATH' in os.environ:
    sys.path.insert(0, os.path.join(os.environ['RESOURCEPATH']))

# The following line allows us to import user plug-ins from ~/.virtaal/virtaal_plugins
# (see PluginController.PLUGIN_MODULES)
sys.path.insert(0, pan_app.get_config_dir())

class PluginController(BaseController):
    """This controller is responsible for all plug-in management."""

    __gtype_name__ = 'PluginController'
    __gsignals__ = {
        'plugin-enabled':  (GObject.SignalFlags.RUN_FIRST, None, (TYPE_PYOBJECT,)),
        'plugin-disabled': (GObject.SignalFlags.RUN_FIRST, None, (TYPE_PYOBJECT,)),
    }

    # The following class variables are set for the main plug-in controller.
    # To use this class to manage any other plug-ins, these will (most likely) have to be changed.
    PLUGIN_CLASSNAME = 'Plugin'
    """The name of the class that will be instantiated from the plug-in module."""
    PLUGIN_CLASS_INFO_ATTRIBS = ['description', 'display_name', 'version']
    """Attributes of the plug-in class that contain info about it. Should contain PLUGIN_NAME_ATTRIB."""
    PLUGIN_DIRS = [
        os.path.join(pan_app.get_config_dir(), u'virtaal_plugins'),
        os.path.join(get_unicode(os.path.dirname(__file__)), u'..', u'plugins')
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
    def __init__(self, controller, classname=None):
        GObjectWrapper.__init__(self)

        self.controller = controller
        if classname:
            self.PLUGIN_CLASSNAME = classname
        else:
            # controller is maincontroller
            controller.plugin_controller = self
        self.plugins       = {}
        self.pluginmodules = {}

        if os.name == 'nt':
            self.PLUGIN_DIRS.insert(0, os.path.join(pan_app.main_dir, u'virtaal_plugins'))
        if 'RESOURCEPATH' in os.environ:
            self.PLUGIN_DIRS.insert(0, os.path.join(os.environ['RESOURCEPATH'].decode(sys.getfilesystemencoding()), u'virtaal_plugins'))


    # METHODS #
    def disable_plugin(self, name):
        """Destroy the plug-in with the given name."""
        logging.debug('Disabling plugin: %s' % (name))

        if name in self.plugins:
            self.emit('plugin-disabled', self.plugins[name])
            self.plugins[name].destroy()
            del self.plugins[name]
        if name in self.pluginmodules:
            del self.pluginmodules[name]

    def enable_plugin(self, name):
        """Load the plug-in with the given name and instantiate it."""
        if name in self.plugins:
            return None

        try:
            plugin_class = self._get_plugin_class(name)
            try:
                self.plugins[name] = plugin_class(name, self.controller)
            except PluginUnsupported as pu:
                # Exception.message was a Python 2-only attribute -
                # PluginUnsupported (controllers/baseplugin.py) is a bare
                # Exception subclass with no such attribute in Python 3.
                logging.info(str(pu))
                return None
            self.emit('plugin-enabled', self.plugins[name])
            logging.info('    - ' + getattr(self.plugins[name], self.PLUGIN_NAME_ATTRIB, name))
            return self.plugins[name]
        except Exception as e:
            # the name is unicode which can trigger encoding issues in the
            # logging module, so let's encode it now already
            logging.exception('Failed to load plugin "{}"\n{}'.format(name, e))

        return None

    def get_plugin_info(self, name):
        plugin_class = self._get_plugin_class(name)
        item = {}
        for attrib in self.PLUGIN_CLASS_INFO_ATTRIBS:
            item[attrib] = getattr(plugin_class, attrib, None)
        return item

    def load_plugins(self):
        """Load plugins from the "plugins" directory."""
        self.plugins       = {}
        self.pluginmodules = {}
        disabled_plugins = self.get_disabled_plugins()

        logging.info('Loading plug-ins:')
        for name in self._find_plugin_names():
            if name in disabled_plugins:
                continue
            # We use idle_add(), so that the UI will respond sooner
            GLib.idle_add(self.enable_plugin, name)
        logging.info('Queued all plugins for loading')

    def shutdown(self):
        """Disable all plug-ins."""
        for name in list(self.plugins.keys()):
            self.disable_plugin(name)

    def get_disabled_plugins(self):
        """Returns a list of names of plug-ins that are disabled in the
            configuration.

            This method should be replaced if an instance is not used for
            normal plug-ins."""
        return [plugin_name for (plugin_name, state) in pan_app.settings.plugin_state.items() if state.lower() == 'disabled']

    def _get_plugin_class(self, name):
        if name in self.plugins:
            return self.plugins[name].__class__

        module = None
        for plugin_module in self.PLUGIN_MODULES:
            # The following line makes sure that we have a valid module name to import from
            modulename = '.'.join([part for part in [plugin_module, name] if part])
            try:
                module = __import__(
                    modulename,
                    globals(),              # globals
                    [],                     # locals
                    [self.PLUGIN_CLASSNAME] # fromlist
                )
                break
            except ImportError as ie:
                if not ie.args[0].startswith('No module named') and pan_app.DEBUG:
                    logging.exception('from %s import %s' % (modulename, self.PLUGIN_CLASSNAME))

        if module is None:
            if pan_app.DEBUG:
                logging.exception('Could not find plug-in "%s"' % (name))
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
        return plugin_class

    def _find_plugin_names(self):
        """Look in each of C{self.PLUGIN_MODULES}'s packages for importable
            submodules, via C{pkgutil.iter_modules()} rather than scanning
            C{self.PLUGIN_DIRS} on the filesystem directly - the latter
            always found nothing in a frozen (PyInstaller) build, since
            pure-Python modules are bundled into an archive there, not laid
            out as loose files on disk, so the "plugins" directory simply
            doesn't exist to list. pkgutil.iter_modules() works against a
            package's __path__ either way, frozen or not.
            @note: Hidden files/directories are ignored.
            @note: If a plug-in is in a directory, it's C{self.PLUGIN_CLASSNAME}
                class should be exposed in the plug-in's __init__.py file.
            @returns: A list of module names, assumed to be plug-ins."""
        import importlib
        import pkgutil

        plugin_names = []

        for plugin_module in self.PLUGIN_MODULES:
            try:
                package = importlib.import_module(plugin_module)
            except ImportError:
                continue
            if not hasattr(package, '__path__'):
                continue
            for _finder, name, _ispkg in pkgutil.iter_modules(package.__path__):
                if self._is_wrong_plugin_name(name):
                    continue
                if pan_app.DEBUG or name[0] != u'_':
                    plugin_names.append(name)

        plugin_names = list(set(plugin_names))
        #logging.debug('Found plugins: %s' % (', '.join(plugin_names)))
        return plugin_names

    @staticmethod
    def _is_wrong_plugin_name(name):
        return name.startswith(u'.') or name.startswith(u'test_') or name == '__pycache__'
