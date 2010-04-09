#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009-2010 Zuza Software Foundation
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

"""A TM provider that can query the web service for the Apertium software for
Machine Translation.

http://wiki.apertium.org/wiki/Apertium_web_service
"""

import urllib
# These two json modules are API compatible
try:
    import simplejson as json #should be a bit faster; needed for Python < 2.6
except ImportError:
    import json #available since Python 2.6

from basetmmodel import BaseTMModel, unescape_html_entities

from virtaal.support.httpclient import HTTPClient, RESTRequest


class TMModel(BaseTMModel):
    """This is the translation memory model."""

    __gtype_name__ = 'ApertiumTMModel'
    display_name = _('Apertium')
    description = _('Unreviewed machine translations from Apertium')

    url = "http://api.apertium.org/json"
    default_config = {
        "appid" : "",
    }

    # INITIALISERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        self.language_pairs = []
        self.load_config()

        self.client = HTTPClient()
        self.url_getpairs = "%(url)s/listPairs?appId=%(appid)s" % {"url": self.url, "appid": self.config["appid"]}
        self.url_translate = "%(url)s/translate" % {"url": self.url}
        self.appid = self.config['appid']
        langreq = RESTRequest(self.url_getpairs, '', method='GET', data=urllib.urlencode(''), headers=None)
        self.client.add(langreq)
        langreq.connect(
            'http-success',
            lambda langreq, response: self.got_language_pairs(response)
        )

        super(TMModel, self).__init__(controller)


    # METHODS #
    def query(self, tmcontroller, unit):
        """Send the query to the web service. The response is handled by means
        of a call-back because it happens asynchronously."""
        pair = (self.source_lang, self.target_lang)
        if pair not in self.language_pairs:
            return

        query_str = unit.source
        if self.cache.has_key(query_str):
            self.emit('match-found', query_str, self.cache[query_str])
        else:
            values = {
                'appId': self.appid,
                'q': query_str,
                'langpair': "%s|%s" % (self.source_lang, self.target_lang),
                'markUnknown': "no",
                'format': 'html',
            }
            req = RESTRequest(self.url_translate + "?" + urllib.urlencode(values), '', method='GET', \
                    data=urllib.urlencode(''), headers=None)
            self.client.add(req)
            req.connect(
                'http-success',
                lambda req, response: self.got_translation(response, query_str)
            )

    def got_language_pairs(self, val):
        """Handle the response from the web service to set up language pairs."""
        data = json.loads(val)
        if data['responseStatus'] != 200:
            logging.debug("Failed to get languages:\n%s", (query_str, data['responseDetails']))
            return

        self.language_pairs = [(pair['sourceLanguage'], pair['targetLanguage']) for pair in data['responseData']]

    def got_translation(self, val, query_str):
        """Handle the response from the web service now that it came in."""
        data = json.loads(val)

        if data['responseStatus'] != 200:
            logging.debug("Failed to translate '%s':\n%s", (query_str, data['responseDetails']))
            return

        target = data['responseData']['translatedText']
        target = unescape_html_entities(target)
        if target.endswith("\n") and not query_str.endswith("\n"):
            target = target[:-1]# chop of \n
        match = {
            'source': query_str,
            'target': target,
            #l10n: Try to keep this as short as possible. Feel free to transliterate in CJK languages for optimal vertical display.
            'tmsource': _('Apertium'),
        }
        self.cache[query_str] = [match]

        self.emit('match-found', query_str, [match])
