#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2008 Zuza Software Foundation
#
# This file is part of virtaal.
#
# translate is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with translate; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
import logging

try:
    #from iniparse import ConfigParser
    import iniparse as ConfigParser
except ImportError, e:
    import ConfigParser
import os
import locale, gettext
import pygtk
pygtk.require("2.0")
_ = gettext.gettext

from __version__ import ver

x_generator = 'VirTaal ' + ver
default_config = "~/.locamotion/virtaal.ini"

def name():
    # pwd is only available on UNIX
    try:
        import pwd
        import getpass
    except ImportError, _e:
        return u""
    return pwd.getpwnam(getpass.getuser())[4]

class Settings:
    """Handles loading/saving settings from/to a configuration file."""

    sections = ["translator", "general", "language", "undo"]

    translator =    {
            "name": name(),
            "email": "",
            "team": "",
    }
    general =       {
            "lastdir": "",
            "windowheight": 620,
            "windowwidth": 400,
    }
    language =      {
            "uilang": None,
            "sourcelang": "en",
            "contentlang": None,
    }
    undo = {
            "depth": 50,
    }

    def __init__(self, filename = None):
        """Load settings, using the given or default filename"""
        if not filename:
            self.filename = os.path.expanduser(default_config)
        else:
            self.filename = filename

        try:
            lang = locale.getlocale()[0]
            self.language["uilang"] = lang
            self.language["contentlang"] = lang
        except:
            logging.info(_("Could not get locale"))
        self.config = ConfigParser.ConfigParser()

        for section in self.sections:
            if not self.config.has_section(section):
                self.config.add_section(section)

    def read(self):
        """Read the configuration file and set the dictionaries up."""
        self.config.read(self.filename)

        for key, value in self.config.items("translator"):
            self.translator[key] = value
        for key, value in self.config.items("general"):
            self.general[key] = value
        for key, value in self.config.items("language"):
            self.language[key] = value
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
