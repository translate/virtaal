#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import sys

from virtaal.common.platform import Platform
from virtaal.support import helperprocess


def test_command_uses_run_module_when_frozen(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(frozen=True))

    assert helperprocess.command('virtaal.support.x') == [sys.executable, '--run-module', 'virtaal.support.x']


def test_command_uses_module_flag_when_not_frozen(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(frozen=False))

    assert helperprocess.command('virtaal.support.x') == [sys.executable, '-m', 'virtaal.support.x']


def test_env_adds_pythonpath_when_not_frozen(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(frozen=False))
    monkeypatch.setattr(helperprocess.os, 'environ', {'PYTHONPATH': '/existing'})

    env = helperprocess.env()

    assert '/existing' in env['PYTHONPATH']
    assert env['PYTHONPATH'] != '/existing'  # something was prepended


def test_env_leaves_pythonpath_untouched_when_frozen(monkeypatch):
    monkeypatch.setattr(helperprocess, 'platform', Platform(frozen=True))
    monkeypatch.setattr(helperprocess.os, 'environ', {'PYTHONPATH': '/existing'})

    assert helperprocess.env()['PYTHONPATH'] == '/existing'
