#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2008 Zuza Software Foundation
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

import logging

try:
    import iniparse as ConfigParser
except ImportError, e:
    import ConfigParser
import os
import sys
import locale, gettext
gettext.install("virtaal", unicode=1)

from __version__ import ver


x_generator = 'Virtaal ' + ver
default_config_name = "virtaal.ini"

def get_config_dir():
    if os.name == 'nt':
        confdir = os.path.join(os.environ['APPDATA'], 'Virtaal')
    else:
        confdir = os.path.expanduser('~/.virtaal')

    if not os.path.exists(confdir):
        os.makedirs(confdir)

    return confdir

def name():
    # pwd is only available on UNIX
    try:
        import pwd
        import getpass
    except ImportError, _e:
        return u""
    return pwd.getpwnam(getpass.getuser())[4].split(",")[0]


class Settings:
    """Handles loading/saving settings from/to a configuration file."""

    sections = ["translator", "general", "language", "plugin_state", "undo"]

    translator =    {
            "name": name(),
            "email": "",
            "team": "",
    }
    general =       {
            "lastdir": "",
            "windowheight": 620,
            "windowwidth": 400,
            "terminology-dir": "",
    }
    language =      {
            "uilang": None,
            "sourcelang": "en",
            "contentlang": None,
            "sourcefont": "mono 9",
            "targetfont": "mono 9",
            "nplurals": 0,
            "plural": None,
    }
    plugin_state =  {
        "HelloWorld": "disabled"
    }
    undo = {
            "depth": 50,
    }

    def __init__(self, filename = None):
        """Load settings, using the given or default filename"""
        if not filename:
            self.filename = os.path.join(get_config_dir(), default_config_name)
        else:
            self.filename = filename
            if not os.path.isfile(self.filename):
                raise Exception

        try:
            lang = locale.getdefaultlocale()[0]
            self.language["uilang"] = lang
            self.language["contentlang"] = lang
        except:
            logging.info("Could not get locale")
        self.config = ConfigParser.ConfigParser()
        self.read()

    def read(self):
        """Read the configuration file and set the dictionaries up."""
        self.config.read(self.filename)
        for section in self.sections:
            if not self.config.has_section(section):
                self.config.add_section(section)

        for key, value in self.config.items("translator"):
            self.translator[key] = value
        for key, value in self.config.items("general"):
            self.general[key] = value
        for key, value in self.config.items("language"):
            self.language[key] = value
        for key, value in self.config.items("plugin_state"):
            self.plugin_state[key] = value
        for key, value in self.config.items("undo"):
            self.undo[key] = value

    def write(self):
        """Write the configuration file."""
        for key in self.translator:
            self.config.set("translator", key, self.translator[key])
        for key in self.general:
            self.config.set("general", key, self.general[key])
        for key in self.language:
            self.config.set("language", key, self.language[key])
        for key in self.plugin_state:
            self.config.set("plugin_state", key, self.plugin_state[key])
        for key in self.undo:
            self.config.set("undo", key, self.undo[key])

        # make sure that the configuration directory exists
        project_dir = os.path.split(self.filename)[0]
        if not os.path.isdir(project_dir):
            os.makedirs(project_dir)
        file = open(self.filename, 'w')
        self.config.write(file)
        file.close()

settings = Settings()


def get_abs_data_filename(path_parts):
    """Get the absolute path to the given file- or directory name in Virtaal's
        data directory.

        @type  path_parts: list
        @param path_parts: The path parts that can be joined by os.path.join().
        """

    if isinstance(path_parts, str):
        path_parts = [path_parts]

    BASE_DIRS = [
        os.path.dirname(unicode(__file__, sys.getfilesystemencoding())),
        os.path.dirname(unicode(sys.executable, sys.getfilesystemencoding()))
    ]

    DATA_DIRS = [
        ["..", "share"],
        ["..", "..", "share"]
    ]

    for basepath, data_dir in ((x, y) for x in BASE_DIRS for y in DATA_DIRS):
        dir_and_filename = data_dir + path_parts
        datafile = os.path.join(basepath or os.path.dirname(__file__), *dir_and_filename)
        if os.path.exists(datafile):
            return datafile
    raise Exception('Could not find "%s"' % (os.path.join(*path_parts)))

def load_config(filename, section=None):
    """Load the configuration from the given filename (and optional section
        into a dictionary structure.

        @returns: A 2D-dictionary representing the configuration file if no
            section was specified. Otherwise a simple dictionary representing
            the given configuration section."""
    parser = ConfigParser.ConfigParser()
    parser.read(filename)

    if section:
        if section not in parser.sections():
            return {}
        return dict(parser.items(section))

    conf = {}
    for section in parser.sections():
        conf[section] = dict(parser.items(section))
    return conf

def save_config(filename, config, section=None):
    """Save the given configuration data to the given filename and under the
        given section (if specified).

        @param config: A dictionary containing the configuration section data
            if C{section} was specified. Otherwise, if C{section} is not
            specified, it should be a 2D-dictionary representing the entire
            configuration file."""
    parser = ConfigParser.ConfigParser()
    parser.read(filename)

    if section:
        config = {section: config}

    for section, section_conf in config.items():
        if section not in parser.sections():
            parser.add_section(section)
        for key, value in section_conf.items():
            parser.set(section, key, value)

    conffile = open(filename, 'w')
    parser.write(conffile)
    conffile.close()
