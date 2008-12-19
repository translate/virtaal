#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
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
import os
import subprocess

import gobject

from translate.services import tmclient

from virtaal.common import pan_app
from virtaal.plugins.tm.basetmmodel import BaseTMModel

class TMModel(BaseTMModel):
    """This is the translation memory model."""

    __gtype_name__ = 'LocalTMModel'

    default_config = {
        "tmserver_bind" : "localhost",
        "tmserver_port" : "8080",
        "tm_store" : os.path.join(pan_app.get_config_dir(), "tm.po")
        }

    # INITIALIZERS #
    def __init__(self, controller):
        self.load_config()
        command = ["tmserver.py",
                   "-b", self.config["tmserver_bind"],
                   "-p", self.config["tmserver_port"],
                   "-t", self.config["tm_store"],
                   ]

        self.tmserver = subprocess.Popen(command)
        url = "http://%s:%s/tmserver" % (self.config["tmserver_bind"], self.config["tmserver_port"])

        self.tmclient = tmclient.TMClient(url)
        super(TMModel, self).__init__(controller)

    # METHODS #
    def query(self, tmcontroller, query_str):
        if self.cache.has_key(query_str):
            self.emit('match-found', query_str, self.cache[query_str])
        else:
            self.tmclient.translate_unit(query_str, self.handle_matches)

    def handle_matches(self, widget, query_str, matches):
        self.cache[query_str] = matches
        self.emit('match-found', query_str, matches)

    def destroy(self):
        if os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.TerminateProcess(int(self.tmserver._handle), -1)
        else:
            import signal
            os.kill(self.tmserver.pid, signal.SIGTERM)
