#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
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
import logging
import urllib
import pycurl
# These two json modules are API compatible
try:
    import simplejson as json #should be a bit faster; needed for Python < 2.6
except ImportError:
    import json #available since Python 2.6

from translate.lang import data
from translate.search.lshtein import LevenshteinComparer

from virtaal.support.httpclient import HTTPClient, RESTRequest

class OpenTranClient(gobject.GObject, HTTPClient):
    """CRUD operations for TM units and stores"""

    __gtype_name__ = 'OpenTranClient'
    __gsignals__ = {
        'source-lang-changed': (gobject.SIGNAL_RUN_LAST, None, (str,)),
        'target-lang-changed': (gobject.SIGNAL_RUN_LAST, None, (str,)),
    }

    def __init__(self, max_candidates=3, min_similarity=75, max_length=1000):
        gobject.GObject.__init__(self)
        HTTPClient.__init__(self)

        self.max_candidates = max_candidates
        self.min_similarity = min_similarity
        self.comparer = LevenshteinComparer(max_length)
        self.last_suggestions = None  # used by the open-tran terminology backend

        self._languages = set()

        self.source_lang = None
        self.target_lang = None
        #detect supported language

        self.url_getlanguages = 'http://open-tran.eu/json/supported'
        self.url_translate = 'http://%s.%s.open-tran.eu/json/suggest'
        langreq = RESTRequest(self.url_getlanguages, id='', method='GET', data=urllib.urlencode(''))
        self.add(langreq)
        langreq.connect(
            'http-success',
            lambda langreq, response: self.got_languages(response)
        )

    def got_languages(self, val):
        """Handle the response from the web service to set up language pairs."""
        data = self._loads_safe(val)
        self._languages = set(data)
        self.set_source_lang(self.source_lang)
        self.set_target_lang(self.target_lang)

    def translate_unit(self, unit_source, callback=None):
        if self.source_lang is None or self.target_lang is None:
            return

        if not self._languages:
            # for some reason we don't (yet) have supported languages
            return

        query_str = unit_source
        request = RESTRequest(self.url_translate % (self.source_lang, self.target_lang), id=query_str, method='GET', \
                data=urllib.urlencode(''))
        self.add(request)
        def call_callback(request, response):
            return callback(
                request, request.id, self.format_suggestions(request.id, response)
            )

        if callback:
            request.connect("http-success", call_callback)

    def set_source_lang(self, language):
        language = language.lower().replace('-', '_').replace('@', '_')
        if not self._languages:
            # for some reason we don't (yet) have supported languages
            self.source_lang = language
            # we'll redo this once we have languages
            return

        if language in self._languages:
            self.source_lang = language
            logging.debug("source language %s supported" % language)
            self.emit('source-lang-changed', self.source_lang)
        else:
            lang = data.simplercode(language)
            if lang:
                self.set_source_lang(lang)
            else:
                self.source_lang = None
                logging.debug("source language %s not supported" % language)

    def set_target_lang(self, language):
        language = language.lower().replace('-', '_').replace('@', '_')
        if not self._languages:
            # for some reason we don't (yet) have supported languages
            self.target_lang = language
            # we'll redo this once we have languages
            return

        if language in self._languages:
            self.target_lang = language
            logging.debug("target language %s supported" % language)
            self.emit('target-lang-changed', self.target_lang)
        else:
            lang = data.simplercode(language)
            if lang:
                self.set_target_lang(lang)
            else:
                self.target_lang = None
                logging.debug("target language %s not supported" % language)

    def _loads_safe(self, response):
        """Does the loading of the JSON response, but handles exceptions."""
        try:
            data = json.loads(response)
        except Exception, exc:
            logging.debug('JSON exception: %s' % (exc))
            return None
        return data

    def format_suggestions(self, id, response):
        """clean up open tran suggestion and use the same format as tmserver"""
        suggestions = self._loads_safe(response)
        if not suggestions:
            return []
        id = data.forceunicode(id)
        self.last_suggestions = suggestions  # we keep it for the terminology back-end
        results = []
        for suggestion in suggestions:
            #check for fuzzyness at the 'flag' member:
            for project in suggestion['projects']:
                if project['flags'] == 0:
                    break
            else:
                continue
            result = {}
            result['target'] = data.forceunicode(suggestion['text'])
            result['tmsource'] = suggestion['projects'][0]['name']
            result['source'] = data.forceunicode(suggestion['projects'][0]['orig_phrase'])
            #open-tran often gives too many results with many which can't really be
            #considered to be suitable for translation memory
            result['quality'] = self.comparer.similarity(id, result['source'], self.min_similarity)
            if result['quality'] >= self.min_similarity:
                results.append(result)
        results.sort(key=lambda match: match['quality'], reverse=True)
        results = results[:self.max_candidates]
        return results
