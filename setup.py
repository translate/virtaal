#!/usr/bin/env python

from distutils.core import setup, Distribution, Command
from virtaal.__version__ import ver as virtaal_version
import glob
import os
import os.path as path

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
        ('data', glob.glob(path.join("data", "*"))),
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

##Create an array with all the locale filenames
#I18NFILES = []
#for filepath in glob.glob("locale/*/LC_MESSAGES/*.mo"):
#    targetpath = path.dirname(path.join("share/", filepath))
#    I18NFILES.append((targetpath, [filepath]))

def map_data_file (data_file):
    """remaps a data_file (could be a directory) to a different location
    This version gets rid of Lib\\site-packages, etc"""

    data_parts = data_file.split(os.sep)
    if data_parts[:2] == ["Lib", "site-packages"]:
        data_parts = data_parts[2:]
        if data_parts:
            data_file = path.join(*data_parts)
        else:
            data_file = ""
    if data_parts[:1] == ["translate"]:
        data_parts = data_parts[1:]
        if data_parts:
            data_file = path.join(*data_parts)
        else:
            data_file = ""
    return data_file

def remap_data_files(self, data_files):
    """maps the given data files to different locations using external map_data_file function"""
    new_data_files = []

    for f in data_files:
        if type(f) in (str, unicode):
            f = map_data_file(f)
        else:
            datadir, files = f
            datadir = map_data_file(datadir)
            if datadir is None:
                f = None
            else:
                f = datadir, files
        if f is not None:
            new_data_files.append(f)
    return new_data_files

class BuildWin32Exe(build_exe):
    """distutils py2exe-based class that builds the exe file(s) but allows mapping data files"""

    # Override
    def reinitialize_command(self, command, reinit_subcommands=0):
        if command == "install_data":
            install_data = build_exe.reinitialize_command(self, command, reinit_subcommands)
            install_data.data_files = self.remap_data_files(install_data.data_files)
            return install_data
        return build_exe.reinitialize_command(self, command, reinit_subcommands)

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
    if py2exe != None:
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
                "py2exe":    BuildWin32Exe,
#                "innosetup": build_win32_installer
            }
        })
    return options

def add_platform_specific_options(options):
    # For now, we only have win32 to worry about
    return add_win32_options(options)

options = add_platform_specific_options(options)

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
