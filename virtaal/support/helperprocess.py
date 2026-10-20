#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Running one of Virtaal's own modules, or another program, in a child
process."""

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


# Set by PyInstaller's GTK hooks and pyi_rth_appimage.py to files outside
# the bundle.
_BUNDLE_FILES = ('GDK_PIXBUF_MODULE_FILE', 'GTK_IM_MODULE_FILE')


def host_env(environ=None, bundle=None):
    """The environment for another program (a browser, xdg-open): without
        the frozen Linux build's own library and GTK paths, which would
        make it load the bundle's libraries instead of its own."""
    env = dict(os.environ if environ is None else environ)
    if not (platform.is_frozen and platform.is_linux):
        return env
    bundle = bundle if bundle is not None else getattr(sys, '_MEIPASS', None)
    if not bundle:
        return env
    bundle = bundle.rstrip('/') + '/'
    # pyi_rth_appimage.py's own choice, not the user's.
    if env.pop('_VIRTAAL_SET_GTK_IM_MODULE', None):
        env.pop('GTK_IM_MODULE', None)
    for name in list(env):
        if name.startswith('_PYI_') or name in _BUNDLE_FILES:
            del env[name]
            continue
        if name.endswith('_ORIG'):
            continue
        paths = env[name].split(':')
        kept = [p for p in paths if not (p + '/').startswith(bundle)]
        if kept == paths:
            continue
        if any(kept):
            env[name] = ':'.join(kept)
        else:
            del env[name]
    # PyInstaller keeps what it replaced.
    for name in [n for n in env if n.endswith('_ORIG')]:
        env[name[:-len('_ORIG')]] = env.pop(name)
    return env
