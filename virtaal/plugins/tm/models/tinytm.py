#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2011 Zuza Software Foundation
# Copyright 2014 F Wolff
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

from gi.repository import Gtk

from basetmmodel import BaseTMModel
from virtaal.controllers.baseplugin import PluginUnsupported

MAX_ERRORS = 5


class TMModel(BaseTMModel):
    """This is a TinyTM translation memory model.

    Built according the l{protocol<http://tinytm.org/en/technology/protocol.html>} defined
    by the TinyTM project.
    """

    __gtype_name__ = 'TinyTmTMModel'
    display_name = _('TinyTM')
    description = _('A TinyTM translation memory server')

    default_config = {
        "server":   "localhost",
        "username": "postgres",
        "password": "",
        "database": "tinytm",
        "port": "5432",
    }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        self.load_config()

        try:
            import psycopg2
            self.psycopg2 = psycopg2
        except ImportError:
            raise PluginUnsupported("The psycopg2 package is required for TinyTM")

        # We count errors so that we can disable the plugin if it experiences
        # multiple problems. If still negative, it means we were never able to
        # connect, so we can disable the plugin completely.
        self._errors = -1

        self._db_con = self.psycopg2.connect(
            database=self.config["database"],
            user=self.config["username"],
            password=self.config["password"],
            host=self.config["server"],
            async=1,
            port=self.config["port"],
        )
        self.wait()
        self._errors = 0

        super(TMModel, self).__init__(controller)


    # METHODS #
    def query(self, tmcontroller, unit):
        if self._db_con.closed or self._db_con.isexecuting():
            # Two cursors can't execute concurrently on an asynchronous
            # connection. We could try to cancel the old one, but if it hasn't
            # finished yet, it might be busy. So let's rather not pile on
            # another query to avoid overloading the server.
            return

        query_str = unit.source
        matches = []
        cursor = self._db_con.cursor()
        try:
            cursor.execute(
                """SELECT * FROM tinytm_get_fuzzy_matches(%s, %s, %s, '', '')""",
                (self.source_lang, self.target_lang, query_str.encode('utf-8'))
            )
            # You can connect to any postgres database and use this for basic
            # testing:
            #cursor.execute("""select pg_sleep(2); SELECT 99, 'source', 'target';""")
            # Uncomment this if you don't trust the results
            #cursor.execute("""SELECT * FROM tinytm_get_fuzzy_matches('en', 'de', 'THE EUROPEAN ECONOMIC COMMUNITY', '', '')""")
        except self.psycopg2.Error, e:
            self.error(e)
        self.wait()
        for result in cursor.fetchall():
            quality, source, target = result[:3]
            if not isinstance(target, unicode):
                target = unicode(target, 'utf-8')
            matches.append({
                'source': source,
                'target': target,
                'quality': quality,
                'tmsource': self.display_name,
            })

        self.emit('match-found', query_str, matches)

    def wait(self):
        import select
        while 1:
            while Gtk.events_pending():
                Gtk.main_iteration()
            try:
                state = self._db_con.poll()
            except self.psycopg2.Error, e:
                self.error(e)

            if state == self.psycopg2.extensions.POLL_OK:
                break
            elif state == self.psycopg2.extensions.POLL_WRITE:
                select.select([], [self._db_con.fileno()], [], 0.05)
            elif state == self.psycopg2.extensions.POLL_READ:
                select.select([self._db_con.fileno()], [], [], 0.05)
            else:
                self.error()
                raise self.psycopg2.OperationalError("poll() returned %s" % state)

    def error(self, e=None):
        if self._errors < 0:
            # We're still busy initialising
            raise PluginUnsupported("Unable to connect to the TinyTM server.")

        if e:
            logging.error("[%s] %s" % (e.pgcode, e.pgerror))
        self._errors += 1
        if self._errors > MAX_ERRORS:
            self._db_con.close()

    def destroy(self):
        super(TMModel, self).destroy()
        self._db_con.close()
