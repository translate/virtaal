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

import gobject
import pgsql

from virtaal.plugins.tm.basetmmodel import BaseTMModel
from virtaal.common import pan_app

class TMModel(BaseTMModel):
    """This is a TinyTM translation memory model.

    Built according the l{protocol<http://tinytm.org/en/technology/protocol.html>} defined 
    by the TinyTM project.
    """

    __gtype_name__ = 'TinyTmTMModel'

    default_config = {
        "server": "www.tinytm.org",
        "username": "bbigboss",
        "password": "ben",
        "database": "projop",
    }

    # INITIALIZERS #
    def __init__(self, controller):
        super(TMModel, self).__init__(controller)
        self.load_config()

        self._from = pan_app.settings.language["sourcelang"]
        self._to = pan_app.settings.language["contentlang"]

        self._db = pgsql.connect(database=self.config["database"], user=self.config["username"], password=self.config["password"], host=self.config["server"])


    # METHODS #
    def query(self, tmcontroller, query_str):
        matches = []
        # Uncomment this if you don't trust the results
        #results = self._db.execute("""select * from tinytm_get_fuzzy_matches('en', 'de', 'THE EUROPEAN ECONOMIC COMMUNITY', '', '')""")
        results = self._db.execute("""select * from tinytm_get_fuzzy_matches($1, $2, $3, '', '')""", (self._from, self._to, query_str))
        for result in results.fetchall():
            #print result
            matches.append({
                'source': result[1],
                'target': result[2],
                'quality': result[0] 
            })

        self.emit('match-found', query_str, matches)

    def destroy(self):
        self.save_config()
        self._db.close()
