#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import json
import logging
from urllib.parse import quote_plus

import pycurl

from virtaal.common.utils import get_unicode
from virtaal.support.httpclient import HTTPClient, RESTRequest

from .basetmmodel import BaseTMModel, unescape_html_entities

# Some codes are weird or can be reused for others
code_translation = {
    'fl': 'tl', # Filipino -> Tagalog
    'he': 'iw', # Weird code Google uses for Hebrew
    'nb': 'no', # Google maps no (Norwegian) to its Norwegian (Bokmål) (nb) translator
}

virtaal_referrer = "http://virtaal.org/"

class TMModel(BaseTMModel):
    """This is a Google Translate translation memory model.

    The plugin uses the U{Google AJAX Languages API<http://code.google.com/apis/ajaxlanguage/>}
    to query Google's machine translation services.  The implementation makes use of the
    U{RESTful<http://code.google.com/apis/ajaxlanguage/documentation/#fonje>} interface for
    Non-JavaScript environments.
    """

    __gtype_name__ = 'GoogleTranslateTMModel'
    #l10n: The name of Google Translate in your language (translated in most languages). See http://translate.google.com/
    display_name = _('Google Translate')
    description = _("Unreviewed machine translations from Google's translation service")
    default_config = {'api_key': ''}

    translate_url = "https://www.googleapis.com/language/translate/v2?key=%(key)s&q=%(message)s&source=%(from)s&target=%(to)s"
    languages_url = "https://www.googleapis.com/language/translate/v2/languages?key=%(key)s"

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        super().__init__(controller)
        self.load_config()
        if not self.config['api_key']:
            self._disable_all("An API key is needed to use the Google Translate plugin")
            return
        self.client = HTTPClient()
        self._languages = set()
        langreq = RESTRequest(self.url_getlanguages % self.config, '')
        self.client.add(langreq)
        langreq.connect(
            'http-success',
            lambda langreq, response: self.got_languages(response)
        )

    # METHODS #
    def query(self, tmcontroller, unit):
        query_str = unit.source
        # Google's Terms of Service says the whole URL must be less than "2K"
        # characters.
        query_str = query_str[:2000 - len(self.translate_url)]
        source_lang = code_translation.get(self.source_lang, self.source_lang).replace('_', '-')
        target_lang = code_translation.get(self.target_lang, self.target_lang).replace('_', '-')
        if source_lang not in self._languages or target_lang not in self._languages:
            logging.debug('language pair not supported: %s => %s' % (source_lang, target_lang))
            return

        if query_str in self.cache:
            self.emit('match-found', query_str, self.cache[query_str])
        else:
            real_url = self.translate_url % {
                'key':     self.config['api_key'],
                'message': quote_plus(query_str.encode('utf-8')),
                'from':    source_lang,
                'to':      target_lang,
            }

            req = RESTRequest(real_url, '')
            self.client.add(req)
            # Google's Terms of Service says we need a proper HTTP referrer
            req.curl.setopt(pycurl.REFERER, virtaal_referrer)
            req.connect(
                'http-success',
                lambda req, response: self.got_translation(response, query_str)
            )
            req.connect(
                'http-client-error',
                lambda req, response: self.got_error(response, query_str)
            )
            req.connect(
                'http-server-error',
                lambda req, response: self.got_error(response, query_str)
            )

    def got_translation(self, val, query_str):
        """Handle the response from the web service now that it came in."""
        # In December 2011 version 1 of the API was deprecated, and we had to
        # release code to handle the eminent disappearance of the API. Although
        # version 2 is now supported, the code is a bit more careful (as most
        # code probably should be) and in case of error we make the list of
        # supported languages empty so that no unnecessary network activity is
        # performed if we can't communicate with the available API any more.
        try:
            data = json.loads(val)
            # We try to access the members to validate that the dictionary is
            # formed in the way we expect.
            data['data']
            data['data']['translations']
            text = data['data']['translations'][0]['translatedText']
        except Exception as e:
            self._disable_all("Error with json response: %s" % e)
            return

        target_unescaped = unescape_html_entities(text)
        target_unescaped = get_unicode(target_unescaped, 'utf-8')
        match = {
            'source': query_str,
            'target': target_unescaped,
            #l10n: Try to keep this as short as possible. Feel free to transliterate.
            'tmsource': _('Google')
        }
        self.cache[query_str] = [match]
        self.emit('match-found', query_str, [match])

    def got_languages(self, val):
        """Handle the response from the web service to set up language pairs."""
        try:
            data = json.loads(val)
            data['data']
            languages = data['data']['languages']
        except Exception as e:
            self._disable_all("Error with json response: %s" % e)
            return
        self._languages = set([l['language'] for l in languages])

    def got_error(self, val, query_str):
        self._disable_all("Got an error response: %s" % val)

    def _disable_all(self, reason):
        self._languages = set()
        logging.debug("Stopping all queries for Google Translate. %s" % reason)
