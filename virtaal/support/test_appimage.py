#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os

from virtaal.support import appimage

_SOURCE = """[Desktop Entry]
Version=1.0
Type=Application
Name=Virtaal
Name[af]=Virtaal
TryExec=virtaal
Exec=virtaal %f
Icon=io.github.translate.Virtaal
MimeType=text/x-gettext-translation;application/x-po;
# Not yet supported
# application/x-sdf;
Categories=Development;Translation;GTK;
"""


def _bundle(tmp_path):
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    (bundle / 'io.github.translate.Virtaal.desktop').write_text(_SOURCE, encoding='utf-8')
    (bundle / 'io.github.translate.Virtaal.png').write_bytes(b'png')
    return bundle


def test_desktop_entry_points_at_the_appimage():
    entry = appimage.desktop_entry(_SOURCE, '/home/u/Apps/Virtaal.AppImage', '/home/u/icon.png')

    assert entry.splitlines()[:5] == [
        '[Desktop Entry]',
        'Exec="/home/u/Apps/Virtaal.AppImage" %f',
        'TryExec=/home/u/Apps/Virtaal.AppImage',
        'Icon=/home/u/icon.png',
        'StartupWMClass=Virtaal',
    ]
    assert 'Name[af]=Virtaal' in entry
    assert 'MimeType' not in entry
    assert 'Exec=virtaal' not in entry


def test_desktop_entry_quotes_the_exec_path():
    entry = appimage.desktop_entry(_SOURCE, '/home/u/my "apps"/$x 100%.AppImage', '/i.png')

    assert r'Exec="/home/u/my \"apps\"/\$x 100%%.AppImage" %f' in entry


def test_integrate_installs_the_entry_and_icon(tmp_path):
    data = tmp_path / 'data'

    appimage.integrate('/home/u/Virtaal.AppImage', str(_bundle(tmp_path)), str(data))

    entry = (data / 'applications' / 'virtaal-appimage.desktop').read_text(encoding='utf-8')
    icon = data / 'icons' / 'hicolor' / '256x256' / 'apps' / 'virtaal-appimage.png'
    assert 'TryExec=/home/u/Virtaal.AppImage' in entry
    assert 'Icon=%s' % icon in entry
    assert icon.read_bytes() == b'png'


def test_integrate_follows_a_moved_appimage(tmp_path):
    bundle, data = str(_bundle(tmp_path)), str(tmp_path / 'data')
    appimage.integrate('/old/Virtaal.AppImage', bundle, data)

    appimage.integrate('/new/Virtaal.AppImage', bundle, data)

    with open(os.path.join(data, 'applications', 'virtaal-appimage.desktop'), encoding='utf-8') as f:
        assert 'TryExec=/new/Virtaal.AppImage' in f.read()


def test_integrate_without_an_appimage_does_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv('APPIMAGE', raising=False)

    appimage.integrate(None, str(_bundle(tmp_path)), str(tmp_path / 'data'))

    assert not (tmp_path / 'data').exists()


def test_integrate_only_warns_when_it_cannot_write(tmp_path, caplog):
    data = tmp_path / 'data'
    data.write_text('a file, not a directory')

    appimage.integrate('/home/u/Virtaal.AppImage', str(_bundle(tmp_path)), str(data))

    assert "menu entry" in caplog.text
