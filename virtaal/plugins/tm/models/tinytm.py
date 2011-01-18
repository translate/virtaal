#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2011 Zuza Software Foundation
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

from virtaal.common import pan_app

from basetmmodel import BaseTMModel


class TMModel(BaseTMModel):
    """This is a TinyTM translation memory model.

    Built according the l{protocol<http://tinytm.org/en/technology/protocol.html>} defined
    by the TinyTM project.
    """

    __gtype_name__ = 'TinyTmTMModel'
    display_name = _('TinyTM')
    description = _('A TinyTM translation memory server')

    default_config = {
        "server":   "www.tinytm.org",
        "username": "bbigboss",
        "password": "ben",
        "database": "projop",
    }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        self.load_config()

        try:
            import psycopg2 as psycopg
        except ImportError:
            import psycopg

        self._db_con = psycopg.connect(
            database=self.config["database"],
            user=self.config["username"],
            password=self.config["password"],
            host=self.config["server"]
        )

        super(TMModel, self).__init__(controller)


    # METHODS #
    def query(self, tmcontroller, unit):
        query_str = unit.source
        matches = []
        cursor = self._db_con.cursor()
        # Uncomment this if you don't trust the results
        #cursor.execute("""SELECT * FROM tinytm_get_fuzzy_matches('en', 'de', 'THE EUROPEAN ECONOMIC COMMUNITY', '', '')""")
        try:
            cursor.execute(
                """SELECT * FROM tinytm_get_fuzzy_matches(%s, %s, %s, '', '')""",
                (self.source_lang, self.target_lang, query_str.encode('utf-8'))
            )
        except psycopg.Error, e:
            logging.error("[%s] %s" % (e.pgcode, e.pgerror))
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

    def destroy(self):
        super(TMModel, self).destroy()
        self._db_con.close()
