#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 Zuza Software Foundation
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

"""A TM provider that can query the web service for Micrsoft Translator
Machine Translations."""

import urllib

from basetmmodel import BaseTMModel

from virtaal.support.httpclient import HTTPClient, RESTRequest


class TMModel(BaseTMModel):
    """This is the translation memory model."""

    __gtype_name__ = 'MicrosoftTranslatorTMModel'
    display_name = _('Microsoft Translator')
    description = _('Unreviewed machine translations from Microsoft Translator')

    default_config = {
        "url" : "http://api.microsofttranslator.com/V1/Http.svc",
        "appid" : "7286B45B8C4816BDF75DC007C1952DDC11C646C1",
    }

    # INITIALISERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        self.languages = []
        self.load_config()

        self.client = HTTPClient()
        self.url_getlanguages = "%(url)s/GetLanguages?appId=%(appid)s" % {"url": self.config['url'], "appid": self.config["appid"]}
        self.url_translate = "%(url)s/Translate" % {"url": self.config['url']}
        self.appid = self.config['appid']
        langreq = RESTRequest(self.url_getlanguages, '', method='GET', data=urllib.urlencode(''), headers=None)
        self.client.add(langreq)
        langreq.connect(
            'http-success',
            lambda langreq, response: self.got_languages(response)
        )

        super(TMModel, self).__init__(controller)


    # METHODS #
    def query(self, tmcontroller, unit):
        """Send the query to the web service. The response is handled by means
        of a call-back because it happens asynchronously."""
        if self.source_lang not in self.languages or self.target_lang not in self.languages:
            return

        query_str = unit.source
        if self.cache.has_key(query_str):
            self.emit('match-found', query_str, self.cache[query_str])
        else:
            values = {
                'appId': self.appid,
                'text': query_str,
                'from': self.source_lang,
                'to': self.target_lang
            }
            req = RESTRequest(self.url_translate + "?" + urllib.urlencode(values), '', method='GET', \
                    data=urllib.urlencode(''), headers=None)
            self.client.add(req)
            req.connect(
                'http-success',
                lambda req, response: self.got_translation(response, query_str)
            )

    def got_languages(self, val):
        """Handle the response from the web service to set up language pairs."""
        # Strip BOM via [1:] and split on DOS line endings
        self.languages = [lang for lang in val.decode('utf-8')[1:].strip().split('\r\n')]

    def got_translation(self, val, query_str):
        """Handle the response from the web service now that it came in."""
        if not isinstance(val, unicode):
            val = unicode(val, 'utf-8')
        match = {
            'source': query_str,
            'target': val,
            #l10n: Try to keep this as short as possible. Feel free to transliterate in CJK languages for optimal vertical display.
            'tmsource': _('Microsoft'),
        }
        self.cache[query_str] = [match]

        self.emit('match-found', query_str, [match])
