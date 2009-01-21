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

import logging
import os
import subprocess
import socket
import random
from translate.services import tmclient

from virtaal.common import pan_app

from basetmmodel import BaseTMModel


class TMModel(BaseTMModel):
    """This is the translation memory model."""

    __gtype_name__ = 'LocalTMModel'
    display_name = _('Local Virtaal TM back-end')

    default_config = {
        "tmserver_bind" : "localhost",
        "tmserver_port" : "55555",
        "tmdb" : os.path.join(pan_app.get_config_dir(), "tm.db")
    }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        self.load_config()

        # test if port specified in config is free
        self.config["tmserver_port"] = int(self.config["tmserver_port"])
        if test_port(self.config["tmserver_bind"], self.config["tmserver_port"]):
            port = self.config["tmserver_port"]
        else:
            port = find_free_port(self.config["tmserver_bind"], 49152, 65535)

        command = [
            "tmserver.py",
            "-b", self.config["tmserver_bind"],
            "-p", str(port),
            "-d", self.config["tmdb"],
        ]
        try:
            self.tmserver = subprocess.Popen(command)
            url = "http://%s:%d/tmserver" % (self.config["tmserver_bind"], port)

            self.tmclient = tmclient.TMClient(url)
        except OSError, e:
            message = "Failed to start TM server: %s" % str(e)
            logging.exception('Failed to start TM server')
            raise

        super(TMModel, self).__init__(controller)
        self.controller.main_controller.store_controller.connect("store-saved", self.push_store)


    # METHODS #
    def query(self, tmcontroller, query_str):
        #figure out languages
        if self.cache.has_key(query_str):
            self.emit('match-found', query_str, self.cache[query_str])
        else:
            self.tmclient.translate_unit(query_str, self.source_lang, self.target_lang, self._handle_matches)

    def _handle_matches(self, widget, query_str, matches):
        """Handle the matches when returned from self.tmclient."""
        self.cache[query_str] = matches
        self.emit('match-found', query_str, matches)

    def push_store(self, widget, store):
        """add units in store to tmdb on save"""
        units = []
        for unit in store.units:
            if unit.istranslatable() and unit.istranslated():
                units.append(unit2dict(unit))
        self.tmclient.add_store(store.filename, units, self.source_lang, self.target_lang)
        self.cache = {}
        
    def upload_store(self, widget, store):
        """upload store to tmserver"""
        self.tmclient.upload_store(store, self.source_lang, self.target_lang)
        self.cache = {}

    def destroy(self):
        if os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.TerminateProcess(int(self.tmserver._handle), -1)
        else:
            import signal
            os.kill(self.tmserver.pid, signal.SIGTERM)


def test_port(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        return True
    except socket.error:
        return False

def find_free_port(host, min_port, max_port):
    port_range = range(min_port, max_port)
    random.shuffle(port_range)
    for port in port_range:
        if test_port(host, port):
            return port
    #FIXME: shall we throw an exception if no free port is found?
    return None

def unit2dict(unit):
    return {"source": unit.source, "target": unit.target, "context": unit.getcontext()}
