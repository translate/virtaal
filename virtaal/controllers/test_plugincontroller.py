#!/usr/bin/env python
#
# Copyright 2026 Zuza Software Foundation
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

import os

from virtaal.controllers.plugincontroller import PluginController


def test_resourcepath_plugin_dir_construction(monkeypatch):
    """__init__() called .decode(sys.getfilesystemencoding()) on
    os.environ['RESOURCEPATH'] - a Python 2 idiom (os.environ values
    were bytes there) that raises AttributeError on Python 3, where
    they're already str. RESOURCEPATH is set on every macOS frozen
    launch (translate.misc.file_discovery checks the same var), so
    this crashed PluginController.__init__() there every time."""
    monkeypatch.setenv('RESOURCEPATH', '/tmp/fake_resources')

    # PLUGIN_DIRS is a class attribute that __init__() mutates in
    # place (self.PLUGIN_DIRS.insert(...), no reassignment) - restore
    # it so this test doesn't leave every later PluginController
    # instantiation with a stale extra entry.
    original_dirs = list(PluginController.PLUGIN_DIRS)
    try:
        pc = PluginController(controller=object(), classname='TestPlugin')
        assert pc.PLUGIN_DIRS[0] == os.path.join('/tmp/fake_resources', 'virtaal_plugins')
    finally:
        PluginController.PLUGIN_DIRS[:] = original_dirs
