#!/usr/bin/env python
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import builtins
import logging
import os

import pytest

from virtaal.controllers import plugincontroller
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


def _make_controller():
    pc = PluginController(controller=object(), classname='TestPlugin')
    pc.PLUGIN_MODULES = ['some.candidate.location']
    return pc


def test_get_plugin_class_stays_quiet_when_a_candidate_location_is_missing(monkeypatch, caplog):
    # Several candidate package locations are tried in turn (e.g. the
    # optional virtaal_plugins.* directory before the bundled
    # virtaal.plugins.* one) - one of them simply not existing at all
    # is expected, not an error worth logging.
    pc = _make_controller()
    real_import = builtins.__import__
    def fake_import(name, *a, **k):
        if name.startswith('some.candidate.location'):
            raise ModuleNotFoundError("No module named 'some'", name='some')
        return real_import(name, *a, **k)
    monkeypatch.setattr('builtins.__import__', fake_import)
    monkeypatch.setattr(plugincontroller.pan_app, 'DEBUG', True)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(Exception, match='Could not find plug-in'):
        pc._get_plugin_class('myplugin')

    assert not any('from ' in r.message and 'import' in r.message for r in caplog.records)


def test_get_plugin_class_logs_a_plugins_own_missing_dependency(monkeypatch, caplog):
    # e.g. _ipython_console needing the optional ipython package - a
    # real, existing plugin module whose own internal import fails,
    # not "no such plugin".
    pc = _make_controller()
    real_import = builtins.__import__
    def fake_import(name, *a, **k):
        if name.startswith('some.candidate.location'):
            raise ModuleNotFoundError("No module named 'ipython'", name='ipython')
        return real_import(name, *a, **k)
    monkeypatch.setattr('builtins.__import__', fake_import)
    monkeypatch.setattr(plugincontroller.pan_app, 'DEBUG', True)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(Exception, match='Could not find plug-in'):
        pc._get_plugin_class('myplugin')

    assert any('from ' in r.message and 'import' in r.message for r in caplog.records)
