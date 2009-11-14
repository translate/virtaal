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

import logging
import urllib
# These two json modules are API compatible
try:
    import simplejson as json #should be a bit faster; needed for Python < 2.6
except ImportError:
    import json #available since Python 2.6

from basetmmodel import BaseTMModel, unescape_html_entities
from virtaal.support.httpclient import HTTPClient, RESTRequest


class TMModel(BaseTMModel):
    """This is a Google Translate translation memory model.

    The plugin uses the xgoogle library (by Peteris Krumins) to query Google
    for a translation. The library can be downloaded from
    http://www.catonmat.net/blog/python-library-for-google-search/.
    """

    __gtype_name__ = 'GoogleTranslateTMModel'
    #l10n: The name of Google Translate in your language (translated in most languages). See http://translate.google.com/
    display_name = _('Google Translate')
    description = _("Unreviewed machine translations from Google's translation service")

    translate_url = "http://ajax.googleapis.com/ajax/services/language/translate?v=1.0&q=%(message)s&langpair=%(from)s%%7C%(to)s"

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        self._init_plugin()
        super(TMModel, self).__init__(controller)
        self.client = HTTPClient()

    def _init_plugin(self):
        try:
            from virtaal.support.xgoogle.translate import Translator, TranslationError, _languages
            self.TranslationError = TranslationError
            self.supported_langs = _languages
        except ImportError, ie:
            raise Exception('Could not import virtaal.support.xgoogle.translate.Translator: %s' % (ie))


    # METHODS #
    def query(self, tmcontroller, query_str):
        if self.source_lang not in self.supported_langs or self.target_lang not in self.supported_langs:
            logging.debug('language pair not supported')
            return

        if self.cache.has_key(query_str):
            self.emit('match-found', query_str, self.cache[query_str])
        else:
            real_url = self.translate_url % {
                    'message': urllib.quote_plus(query_str),
                    'from':    self.source_lang,
                    'to':      self.target_lang,
            }

            req = RESTRequest(real_url, '', method='GET', data=urllib.urlencode(''), headers=None)
            self.client.add(req)
            req.connect(
                'http-success',
                lambda req, response: self.got_translation(response, query_str)
            )

    def got_translation(self, val, query_str):
        """Handle the response from the web service now that it came in."""
        data = json.loads(val)

        if data['responseStatus'] != 200:
            logging.debug("Failed to translate '%s':\n%s", (query_str, data['responseDetails']))
            return

        target_unescaped = unescape_html_entities(data['responseData']['translatedText'])
        match = {
            'source': query_str,
            'target': target_unescaped,
            #l10n: Try to keep this as short as possible. Feel free to transliterate.
            'tmsource': _('Google')
        }
        self.cache[query_str] = [match]
        self.emit('match-found', query_str, [match])
