#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2026 Zuza Software Foundation
# Copyright 2013 F Wolff
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

"""setup.py now only handles what pyproject.toml can't express
declaratively: compiling .mo files from .po sources, and (on Linux)
collecting freedesktop desktop-integration data files. Everything else
- metadata, dependencies, the package list - lives in pyproject.toml.

The old py2exe/InnoSetup and py2app packaging paths that used to live
here are gone entirely, not modernized: both were Python-2-only code
that couldn't even be parsed under Python 3 (the InnoSetup script
generator used `print >> ofi` statement syntax), let alone run. macOS
packaging now lives in devsupport/packaging/macos/, independent of
`pip install .`; Windows packaging is tracked as a separate open item
in ISSUE_TRIAGE.md. The custom `DepCheckInstall` install command is
also gone - it duplicated bin/virtaal's own startup dependency check,
and re-checking importability at *build* time (in a possibly
not-yet-fully-set-up environment) rather than at actual app *startup*
caused real, confusing CI failures during this exact rewrite.
"""

import os
import os.path as path
import sys
from glob import glob

from setuptools import setup

SOURCE_DATA_DIR = 'share'
TARGET_DATA_DIR = 'share'

# Compile .mo files from available .po files. This has to happen here,
# at setup.py's top level, rather than in a proper build hook, because
# data_files (below) needs the resulting file list before `setup()` is
# even called - deferring it cleanly would need a bigger rework of how
# data_files works here than this packaging cleanup is scoped for.
from translate.tools.pocompile import convertmo

mo_files = []
for lang in open(path.join('po', 'LINGUAS'), encoding='utf-8'):
    lang = lang.rstrip()
    po_filename = path.join('po', lang + '.po')
    mo_filename = path.join('mo', lang, 'virtaal.mo')

    if not path.exists(path.join('mo', lang)):
        os.makedirs(path.join('mo', lang))

    convertmo(open(po_filename, 'rb'), open(mo_filename, 'w'), None)

    mo_files.append(
        (path.join(TARGET_DATA_DIR, 'locale', lang, 'LC_MESSAGES'), [mo_filename])
    )

# Build lite files as needed on Win32 and OS X
if os.name == 'nt' or sys.platform == 'darwin':
    for lang in open(path.join('po', 'LINGUAS-lite'), encoding='utf-8'):
        app, lang = lang.rstrip().split('/')
        po_filename = path.join('po', 'lite', app, lang + '.po')
        mo_filename = path.join('mo', lang, app + '.mo')

        if not path.exists(path.join('mo', lang)):
            os.makedirs(path.join('mo', lang))

        convertmo(open(po_filename, 'rb'), open(mo_filename, 'w'), None)

        mo_files.append(
            (path.join(TARGET_DATA_DIR, 'locale', lang, 'LC_MESSAGES'), [mo_filename])
        )

data_files = [
    (path.join(TARGET_DATA_DIR, "virtaal"), glob(path.join(SOURCE_DATA_DIR, "virtaal", "*.*"))),
    (path.join(TARGET_DATA_DIR, "virtaal", "autocorr"), glob(path.join(SOURCE_DATA_DIR, "virtaal", "autocorr", "*"))),
    (path.join(TARGET_DATA_DIR, "icons"), glob(path.join(SOURCE_DATA_DIR, "icons", "*.*"))),
] + mo_files

# Freedesktop desktop-integration files (.desktop, mime, metainfo,
# hicolor icons) - Linux-specific.
if sys.platform not in ('win32', 'darwin'):
    data_files.extend([
        (path.join(TARGET_DATA_DIR, "mime", "packages"), glob(path.join(SOURCE_DATA_DIR, "mime", "packages", "*.xml"))),
        (path.join(TARGET_DATA_DIR, "applications"), glob(path.join(SOURCE_DATA_DIR, "applications", "*.desktop"))),
        (path.join(TARGET_DATA_DIR, "metainfo"), glob(path.join(SOURCE_DATA_DIR, "metainfo", "*.metainfo.xml"))),
    ])
    for size in ("16x16", "24x24", "32x32", "48x48", "64x64", "128x128", "scalable"):
        data_files.append(
            (path.join(TARGET_DATA_DIR, "icons", "hicolor", size, "mimetypes"),
             glob(path.join(SOURCE_DATA_DIR, "icons", "hicolor", size, "mimetypes", "*.*")))
        )

setup(data_files=data_files)
