#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011 Zuza Software Foundation
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
import xmlrpclib

from translate.lang import data

from virtaal.support.httpclient import HTTPClient, HTTPRequest

# Moses handles these characters as spaced out
punc_symbols = ur'''.,?!:;'"“”‘’—)'''
punc_tuples = [(c, u" %s" % c) for c in punc_symbols]


def prepare(query_str):
    query_str = query_str.lower()
    for c, repl in punc_tuples:
        query_str = query_str.replace(c, repl)
    query_str = query_str.replace(u"(", u"( ")
    # Newlines need special handling since Moses doesn't support it:
    query_str = query_str.replace(u"\n", u" __::__ ")
    return query_str

def fixup(source, response):
    source = data.forceunicode(source)
    response = data.forceunicode(response)
    from translate.filters.autocorrect import correct
    tmp = correct(source, response)
    if tmp:
        response = tmp
    response = response.replace(u" __::__ ", "\n")
    # and again for the sake of \n\n:
    response = response.replace(u"__::__ ", "\n")
    response = response.replace(u"( ", u"(")
    for c, repl in punc_tuples:
        response = response.replace(repl, c)
    return response


class MosesClient(gobject.GObject, HTTPClient):
    """A client to communicate with a moses XML RPC servers"""

    __gtype_name__ = 'MosesClient'
    __gsignals__ = {
        'source-lang-changed': (gobject.SIGNAL_RUN_LAST, None, (str,)),
        'target-lang-changed': (gobject.SIGNAL_RUN_LAST, None, (str,)),
    }

    def __init__(self, url):
        gobject.GObject.__init__(self)
        HTTPClient.__init__(self)

        self.url = url + '/RPC2'
        self.multilang = False

    def set_multilang(self, state=True):
        """Enable multilingual support.

        If this is set, the plugin will specify the 'system' parameter when
        communicating with the Moses XML RPC server."""
        self.multilang = state

    def translate_unit(self, unit_source, callback=None, target_language=None):
        if isinstance(unit_source, unicode):
            unit_source = unit_source.encode("utf-8")

        parameters = {
                'text': prepare(unit_source),
        }
        if self.multilang:
            parameters['system'] = target_language

        request_body = xmlrpclib.dumps(
                (parameters,), "translate"
        )
        request = HTTPRequest(
            self.url, "POST", request_body,
            headers=["Content-Type: text/xml", "Content-Length: %s" % len(request_body)],
        )
        request.source_text = unit_source
        self.add(request)

        if callback:
            def call_callback(request, response):
                return callback(
                    request.source_text, self._handle_response(request.source_text, response)
                )
            request.connect("http-success", call_callback)

    def _loads_safe(self, response):
        """Does the loading of the XML-RPC response, but handles exceptions."""
        try:
            (data,), _fish = xmlrpclib.loads(response)
        except xmlrpclib.Fault, exc:
            if "Unknown translation system id" in exc.faultString:
                self.set_multilang(False)
                #TODO: consider redoing the request now that multilang is False
                return None
        except Exception, exc:
            logging.debug('XML-RPC exception: %s' % (exc))
            return None
        return data

    def _handle_response(self, id, response):
        """Use the same format as tmserver."""
        suggestion = self._loads_safe(response)
        if not suggestion:
            return None
        return fixup(id, data.forceunicode(suggestion['text']))
