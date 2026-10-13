#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Running one of Virtaal's own modules in a child process."""

import os
import sys

from virtaal.common.platform import platform


def command(module):
    """The command line that runs C{module} like C{python -m}."""
    # A frozen build's sys.executable is Virtaal's own launcher, which
    # takes --run-module instead of -m (see bin/virtaal).
    if platform.is_frozen:
        return [sys.executable, '--run-module', module]
    return [sys.executable, '-m', module]


def env():
    """The environment for a child process, with Virtaal importable."""
    env = os.environ.copy()
    if not platform.is_frozen:
        import virtaal
        virtaal_parent = os.path.dirname(os.path.dirname(os.path.abspath(virtaal.__file__)))
        env['PYTHONPATH'] = os.pathsep.join(filter(None, [virtaal_parent, env.get('PYTHONPATH', '')]))
    return env
