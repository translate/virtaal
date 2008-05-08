#!/usr/bin/env python

from distutils.core import setup, Distribution, Command
from virtaal.__version__ import ver as virtaal_version
import glob
import os
import os.path as path
import sys

try:
    import py2exe
    build_exe = py2exe.build_exe.py2exe
    Distribution = py2exe.Distribution
except ImportError:
    py2exe = None
    build_exe = Command

classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU General Public License (GPL)",
    "Programming Language :: Python",
    "Topic :: Software Development :: Localization",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Operating System :: OS Independent",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: Unix"
]

options = {
    'data_files': [
        ('share/virtaal', (path.join("data", "virtaal.desktop"), (path.join("data", "virtaal-mimetype.xml")))),
        ('share/virtaal', ("virtaal.png",)),
    ],
    'scripts': [
        "run_virtaal.py"
    ],
    'packages': [
        "virtaal",
        "virtaal.support",
        "virtaal.widgets"
    ],
}

#############################
# WIN 32 specifics

def find_gtk_bin_directory():
    GTK_NAME = "libgtk"
    # Look for GTK in the user's Path as well as in some familiar locations
    paths = os.environ['Path'].split(';') + [r'C:\GTK\bin', r'C:\Program Files\GTK\bin']
    for p in paths:
        files = [path.join(p, f) for f in os.listdir(p) if path.isfile(path.join(p, f)) and f.startswith(GTK_NAME)]
        if len(files) > 0:
            return p
    raise Exception("""Could not find the GTK runtime.
Please place bin directory of your GTK installation in the program path.""")

def find_gtk_files():
    def parent(dir):
        return path.abspath(path.join(path.abspath(dir), '..'))

    def strip_leading_path(leadingPath, p):
        return p[len(leadingPath) + 1:]

    data_files = []
    gtk_path = parent(find_gtk_bin_directory())
    for dir in [path.join(gtk_path, p) for p in ('etc', 'share', 'lib')]:
        for dir_name, _, files in os.walk(dir):
            files = [path.abspath(path.join(dir_name, f)) for f in files]
            if len(files) > 0:
                data_files.append((strip_leading_path(gtk_path, dir_name), files))
    return data_files

def add_win32_options(options):
    """This function is responsible for finding data files and setting options necessary
    to build executables and installers under Windows.

    @return: A 2-tuple (data_files, options), where data_files is a list of Windows
             specific data files (this would include the GTK binaries) and where
             options are the options required by py2exe."""
    if py2exe != None and ('py2exe' in sys.argv or 'innosetup' in sys.argv):
        options['data_files'].extend(find_gtk_files())

        py2exe_options = {
            "packages":   ["encodings", "virtaal"],
            "compressed": True,
            "excludes":   ["PyLucene", "Tkconstants", "Tkinter", "tcl", "translate.misc._csv"],
            "dist_dir":   "virtaal-win32",
            "includes":   ["lxml", "lxml._elementpath", "psyco", "cairo", "pango", "pangocairo", "atk", "gobject"],
            "optimize":   2,
        }
        innosetup_options = py2exe_options.copy()
        options.update({
            "windows": [
                {
                    'script': 'run_virtaal.py',
                    'icon_resources': [(1, "virtaal.ico")],
                }
            ],
            'zipfile':  "virtaal.zip",
            "options": {
                "py2exe":    py2exe_options,
                "innosetup": innosetup_options
            },
            'cmdclass':  {
                "py2exe":    build_exe,
#                "innosetup": build_win32_installer
            }
        })
    return options

#############################
# General functions

def add_platform_specific_options(options):
    # For now, we only have win32 to worry about
    return add_win32_options(options)

def create_manifest(data_files):
    f = open('MANIFEST.in', 'w+')
    for _dest_path, data_file_list in data_files:
        f.write("include ")
        f.write(" ".join(data_file_list))
        f.write("\n")
    f.close()

def main():
    options = add_platform_specific_options(options)
    create_manifest(options['data_files'])
    setup(name="virtaal",
          version=virtaal_version,
          license="GNU General Public License (GPL)",
          description="A tool to create program translations.",
          long_description="""VirTaal is used to create program translations.

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
    main()
