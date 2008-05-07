#!/usr/bin/env python

from distutils.core import setup, Distribution, Command
from virtaal.__version__ import ver as virtaal_version
import os
import glob
import os.path

def path(unix_path_str):
    """Convert a UNIX path to a platform independent path.

    Although distutils will convert UNIX paths to platform independent
    paths, functions like glob.glob won't.

    Naturally this function will only yield expected results for
    relative paths."""
    return os.path.join(*unix_path_str.split('/'))

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

##Create an array with all the locale filenames
#I18NFILES = []
#for filepath in glob.glob("locale/*/LC_MESSAGES/*.mo"):
#    targetpath = os.path.dirname(os.path.join("share/", filepath))
#    I18NFILES.append((targetpath, [filepath]))

dist = setup(name="virtaal",
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
      scripts=["run_virtaal.py"],
      packages=["virtaal", "virtaal.support", "virtaal.widgets"],
      data_files=[
                  ('data', glob.glob(path("data/*"))),
      ])

