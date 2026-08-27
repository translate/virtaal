#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
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

from distutils.core import setup
from virtaal.__version__ import ver as virtaal_version
from glob import glob
import os
import os.path as path
import sys

PRETTY_NAME = "Virtaal"
SOURCE_DATA_DIR = 'share'
TARGET_DATA_DIR = 'share'

virtaal_description="A tool to create program translations."

classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Intended Audience :: End Users/Desktop",
    "Intended Audience :: Information Technology",
    "Programming Language :: Python",
    "Topic :: Software Development :: Localization",
    "Topic :: Text Processing :: Linguistic",
    "Operating System :: OS Independent",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: Unix"
]
#TODO: add Natural Language classifiers

# Compile .mo files from available .po files
from translate.tools.pocompile import convertmo
mo_files = []

for lang in open(path.join('po', 'LINGUAS')):
    lang = lang.rstrip()
    po_filename = path.join('po', lang+'.po')
    mo_filename = path.join('mo', lang, 'virtaal.mo')

    if not path.exists(path.join('mo', lang)):
        os.makedirs(path.join('mo', lang))

    convertmo(open(po_filename), open(mo_filename, 'w'), None)

    mo_files.append(
        ( path.join(TARGET_DATA_DIR, 'locale', lang, 'LC_MESSAGES'), [mo_filename])
    )

# Build lite files as needed on Win32 and OS X
if os.name == 'nt' or sys.platform == 'darwin':
    for lang in open(path.join('po', 'LINGUAS-lite')):
        app, lang = lang.rstrip().split('/')
        po_filename = path.join('po', 'lite', app, lang+'.po')
        mo_filename = path.join('mo', lang, app+'.mo')
    
        if not path.exists(path.join('mo', lang)):
            os.makedirs(path.join('mo', lang))
    
        convertmo(open(po_filename), open(mo_filename, 'w'), None)
    
        mo_files.append(
            ( path.join(TARGET_DATA_DIR, 'locale', lang, 'LC_MESSAGES'), [mo_filename])
        )

# Some of these depend on some files to be built externally before running
# setup.py, like the .xml and .desktop files
options = {
    'data_files': [
        (path.join(TARGET_DATA_DIR, "virtaal"), glob(path.join(SOURCE_DATA_DIR, "virtaal", "*.*"))),
        (path.join(TARGET_DATA_DIR, "virtaal", "autocorr"), glob(path.join(SOURCE_DATA_DIR, "virtaal", "autocorr", "*"))),
        (path.join(TARGET_DATA_DIR, "icons"), glob(path.join(SOURCE_DATA_DIR, "icons", "*.*"))),
    ] + mo_files,
    'scripts': [
        "bin/virtaal",
    ],
    'packages': [
        "virtaal",
        "virtaal.common",
        "virtaal.controllers",
        "virtaal.models",
        "virtaal.modes",
        "virtaal.plugins",
        "virtaal.plugins.lookup",
        "virtaal.plugins.lookup.models",
        "virtaal.plugins.terminology",
        "virtaal.plugins.terminology.models",
        "virtaal.plugins.terminology.models.localfile",
        "virtaal.plugins.tm",
        "virtaal.plugins.tm.models",
        "virtaal.support",
        "virtaal.support.libi18n",
        "virtaal.test",
        "virtaal.views",
        "virtaal.views.widgets"
    ],
}

no_install_files = [
    ['LICENSE', 'maketranslations']
]

no_install_dirs = ['po']

def add_freedesktop_options(options):
    options['data_files'].extend([
        (path.join(TARGET_DATA_DIR, "mime", "packages"), glob(path.join(SOURCE_DATA_DIR, "mime", "packages", "*.xml"))),
        (path.join(TARGET_DATA_DIR, "applications"), glob(path.join(SOURCE_DATA_DIR, "applications", "*.desktop"))),
        (path.join(TARGET_DATA_DIR, "metainfo"), glob(path.join(SOURCE_DATA_DIR, "metainfo", "*.metainfo.xml"))),
    ])
    for dir in ("16x16", "24x24", "32x32", "48x48", "64x64", "128x128", "scalable"):
        options['data_files'].extend([
            (path.join(TARGET_DATA_DIR, "icons", "hicolor", dir, "mimetypes"),
            glob(path.join(SOURCE_DATA_DIR, "icons", "hicolor", dir, "mimetypes", "*.*"))),
        ])
    return options

#############################
# General functions

def add_platform_specific_options(options):
    return add_freedesktop_options(options)

def create_manifest(data_files, extra_files, extra_dirs):
    f = open('MANIFEST.in', 'w+')
    f.write("# informational files")
    for infofile in ("README", "TODO", "ChangeLog", "COPYING", "LICENSE", "*.txt"):
        f.write("global-include %s\n" % infofile)
    for data_file_list in [d[1] for d in data_files] + extra_files:
        if not data_file_list:
            continue
        f.write("include %s\n" % (" ".join( data_file_list )))
    for dir in extra_dirs:
        f.write("graft %s\n" % (dir))
    f.close()

import distutils.command.install
class DepCheckInstall(distutils.command.install.install):
    user_options = distutils.command.install.install.user_options + [
        ('nodepcheck', None, "don't check dependencies"),
    ]

    def initialize_options(self):
        distutils.command.install.install.initialize_options(self)
        self.nodepcheck = False

    def run(self, *args, **kwargs):
        if not self.nodepcheck:
            from virtaal.support import depcheck
            failed = depcheck.check_dependencies()
            if failed:
                print 'Failed dependencies: %s' % (', '.join(failed))
                print 'Use the --nodepcheck option to ignore dependencies.'
                exit(0)
        distutils.command.install.install.run(self, *args, **kwargs)

def main(options):
    options = add_platform_specific_options(options)
    if not 'cmdclass' in options:
        options['cmdclass'] = {}
    options['cmdclass']['install'] = DepCheckInstall
    create_manifest(options['data_files'], no_install_files, no_install_dirs)
    setup(name="virtaal",
          version=virtaal_version,
          license="GPL-2.0-or-later",
          description=virtaal_description,
          long_description="""Virtaal is used to create program translations.

It uses the Translate Toolkit to get access to translation files and therefore
can edit a variety of files (including PO and XLIFF files).""",
          author="Translate.org.za",
          author_email="translate-devel@lists.sourceforge.net",
          url="http://translate.sourceforge.net/wiki/virtaal/index",
          download_url="http://sourceforge.net/project/showfiles.php?group_id=91920&package_id=270877",
          platforms=["any"],
          classifiers=classifiers,
          **options)

if __name__ == '__main__':
    main(options)
