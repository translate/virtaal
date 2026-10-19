#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

# These two json modules are API compatible
try:
    import simplejson as json  #should be a bit faster; needed for Python < 2.6
except ImportError:
    import json  #available since Python 2.6

import logging

import pycurl

from virtaal.support.httpclient import HTTPClient, RESTRequest


def _json_callback(callback):
    """An http-success handler passing the decoded reply to C{callback}.
        A reply that isn't JSON (an error page, an empty or truncated
        body) is logged and dropped instead of raising (#4437)."""
    def handler(widget, response):
        try:
            decoded = json.loads(response)
        except ValueError as exc:
            logging.warning('Ignoring a reply from %s that is not JSON: %s', getattr(widget, 'url', '?'), exc)
            return
        callback(widget, widget.id, decoded)
    return handler


class TMClient(HTTPClient):
    """CRUD operations for TM units and stores"""

    def __init__(self, base_url):
        HTTPClient.__init__(self)
        self.base_url = base_url

    def translate_unit(self, unit_source, source_lang, target_lang, callback=None, params=None):
        """suggest translations from TM"""
        request = RESTRequest(
                self.base_url + "/%s/%s/unit" % (source_lang, target_lang),
                unit_source, "GET",
                user_agent=self.user_agent,
                params=params,
        )
        # TM requests have to finish quickly to be useful. This also helps to
        # avoid buildup in case of network failure
        request.curl.setopt(pycurl.TIMEOUT, 30)
        self.add(request)
        if callback:
            request.connect(
                "http-success",
                _json_callback(callback)
            )

    def add_unit(self, unit, source_lang, target_lang, callback=None):
        request = RESTRequest(
                self.base_url + "/%s/%s/unit" % (source_lang, target_lang),
                unit['source'], "PUT", json.dumps(unit),
                user_agent=self.user_agent)
        self.add(request)
        if callback:
            request.connect(
                "http-success",
                _json_callback(callback)
            )

    def update_unit(self, unit, source_lang, target_lang, callback=None):
        request = RESTRequest(
                self.base_url + "/%s/%s/unit" % (source_lang, target_lang),
                unit['source'], "POST", json.dumps(unit),
                user_agent=self.user_agent)
        self.add(request)
        if callback:
            request.connect(
                "http-success",
                _json_callback(callback)
            )

    def forget_unit(self, unit_source, source_lang, target_lang, callback=None):
        request = RESTRequest(
                self.base_url + "/%s/%s/unit" % (source_lang, target_lang),
                unit_source, "DELETE",
                user_agent=self.user_agent)
        self.add(request)
        if callback:
            request.connect(
                "http-success",
                _json_callback(callback)
            )

    def get_store_stats(self, store, callback=None):
        request = RESTRequest(
                self.base_url + "/store",
                store.filename, "GET",
                user_agent=self.user_agent)
        self.add(request)
        if callback:
            request.connect(
                "http-success",
                _json_callback(callback)
            )

    def upload_store(self, store, source_lang, target_lang, callback=None):
        data = str(store)
        request = RESTRequest(
                self.base_url + "/%s/%s/store" % (source_lang, target_lang),
                store.filename, "PUT", data,
                user_agent=self.user_agent)
        self.add(request)
        if callback:
            request.connect(
                "http-success",
                _json_callback(callback)
            )

    def add_store(self, filename, store, source_lang, target_lang, callback=None):
        request = RESTRequest(
                self.base_url + "/%s/%s/store" % (source_lang, target_lang),
                filename, "POST", json.dumps(store),
                user_agent=self.user_agent)
        self.add(request)
        if callback:
            request.connect(
                "http-success",
                _json_callback(callback)
            )

    def forget_store(self, store, callback=None):
        request = RESTRequest(
                self.base_url + "/store",
                store.filename, "DELETE",
                user_agent=self.user_agent)
        self.add(request)
        if callback:
            request.connect(
                "http-success",
                _json_callback(callback)
            )
