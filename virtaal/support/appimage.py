#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""The AppImage's own menu entry and icon. Desktops show an app's icon
only from an installed .desktop file matching its window, and an
AppImage installs nothing."""

import logging
import os

from virtaal.common.platform import platform

ENTRY_ID = 'virtaal-appimage'
# The window's X11 class and Wayland app ID: the bundled executable's name.
WM_CLASS = 'Virtaal'
_DESKTOP = 'io.github.translate.Virtaal.desktop'
_ICON = 'io.github.translate.Virtaal.png'
# Replaced below. No MimeType: the beta doesn't take over opening files.
_DROPPED_KEYS = ('Exec', 'TryExec', 'Icon', 'MimeType', 'StartupWMClass')


def _quote_exec_arg(path):
    """A path quoted for a desktop entry's Exec key."""
    escaped = path.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    return '"%s"' % escaped.replace('%', '%%')


def desktop_entry(source, appimage, icon):
    """The bundled desktop entry, pointing at this AppImage file and icon.
        TryExec hides the entry once the AppImage is moved or deleted."""
    lines = []
    in_main_group = False
    for line in source.splitlines():
        if line.startswith('['):
            in_main_group = line.strip() == '[Desktop Entry]'
        elif in_main_group and line.split('=', 1)[0].strip() in _DROPPED_KEYS:
            continue
        lines.append(line)
        if line.strip() == '[Desktop Entry]':
            lines += [
                'Exec=%s %%f' % _quote_exec_arg(appimage),
                'TryExec=%s' % appimage,
                'Icon=%s' % icon,
                'StartupWMClass=%s' % WM_CLASS,
            ]
    return '\n'.join(lines) + '\n'


def _write_if_changed(path, data):
    try:
        with open(path, 'rb') as f:
            if f.read() == data:
                return
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)


def integrate(appimage=None, bundle_dir=None, data_home=None):
    """Install or update the AppImage's menu entry and icon in the user's
        data directory."""
    appimage = appimage or os.environ.get('APPIMAGE')
    bundle_dir = bundle_dir or platform.bundle_dir
    data_home = data_home or os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    if not (appimage and bundle_dir):
        return
    try:
        icon = os.path.join(data_home, 'icons', 'hicolor', '256x256', 'apps', ENTRY_ID + '.png')
        with open(os.path.join(bundle_dir, _ICON), 'rb') as f:
            _write_if_changed(icon, f.read())
        with open(os.path.join(bundle_dir, _DESKTOP), encoding='utf-8') as f:
            entry = desktop_entry(f.read(), appimage, icon)
        _write_if_changed(os.path.join(data_home, 'applications', ENTRY_ID + '.desktop'), entry.encode('utf-8'))
    except OSError as e:
        logging.warning("Could not install the AppImage's menu entry: %s", e)
