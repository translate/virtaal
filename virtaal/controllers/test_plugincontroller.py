#!/usr/bin/env python
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

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
