#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""A TM provider that can query the web service for the Apertium software for
Machine Translation.

https://wiki.apertium.org/wiki/Apertium_web_service

Note: the old api.apertium.org/json service (with its appId query parameter)
has been retired; this now targets the APY instance Apertium itself hosts,
which needs no appId.
"""

import json
import logging
from urllib.parse import urlencode

import pycountry

from virtaal.support.httpclient import HTTPClient, RESTRequest

from .basetmmodel import BaseTMModel, unescape_html_entities

# APY codes that pycountry's ISO 639-3 code doesn't give.
APY_LANGUAGES = {
    'bs': 'hbs_BS',
    'hr': 'hbs_HR',
    'ms': 'zlm',
    'sr': 'hbs_SR',
}


def apy_codes(code):
    """APY's possible codes for a Virtaal language code, most specific
        first: ca@valencia gives cat_valencia then cat, pt_BR gives
        por_BR then por. APY lists ISO 639-3 codes (#4664)."""
    base, _, variant = code.replace('@', '_').partition('_')
    language = APY_LANGUAGES.get(base)
    if language is None:
        found = pycountry.languages.get(alpha_2=base) if len(base) == 2 else None
        language = found.alpha_3 if found else base
    codes = [code]
    if variant:
        codes.append(language + '_' + variant)
    codes.append(language)
    codes.append(language.split('_')[0])
    return list(dict.fromkeys(codes))


class TMModel(BaseTMModel):
    """This is the translation memory model."""

    __gtype_name__ = 'ApertiumTMModel'
    display_name = _('Apertium')
    description = _('Unreviewed machine translations from Apertium')

    url = "https://www.apertium.org/apy"

    # INITIALISERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        self.language_pairs = []
        self.load_config()

        self.client = HTTPClient()
        self.url_getpairs = "%(url)s/listPairs" % {"url": self.url}
        self.url_translate = "%(url)s/translate" % {"url": self.url}
        langreq = RESTRequest(self.url_getpairs, '')
        self.client.add(langreq)
        langreq.connect(
            'http-success',
            lambda langreq, response: self.got_language_pairs(response)
        )

        super().__init__(controller)


    # METHODS #
    def query(self, tmcontroller, unit):
        """Send the query to the web service. The response is handled by means
        of a call-back because it happens asynchronously."""
        pair = self._apy_pair()
        if pair is None:
            return

        query_str = unit.source
        if query_str in self.cache:
            self.emit('match-found', query_str, self.cache[query_str])
        else:
            values = {
                'q': query_str,
                'langpair': "%s|%s" % pair,
                'markUnknown': "no",
                'format': 'html',
            }
            req = RESTRequest(self.url_translate + "?" + urlencode(values), '')
            self.client.add(req)
            req.connect(
                'http-success',
                lambda req, response: self.got_translation(response, query_str)
            )

    def _apy_pair(self):
        """The most specific listed APY pair for the current languages, or
            None."""
        for source in apy_codes(self.source_lang or ''):
            for target in apy_codes(self.target_lang or ''):
                if (source, target) in self.language_pairs:
                    return (source, target)
        return None

    def got_language_pairs(self, val):
        """Handle the response from the web service to set up language pairs."""
        try:
            data = json.loads(val)
            if data['responseStatus'] != 200:
                logging.debug("Failed to get languages:\n%s", (data['responseDetails']))
                return
            self.language_pairs = [(pair['sourceLanguage'], pair['targetLanguage']) for pair in data['responseData']]
        except (ValueError, KeyError, TypeError) as exc:
            # Not JSON, or of another shape (#4438).
            logging.warning("Ignoring an Apertium language list it can't read: %s", exc)

    def got_translation(self, val, query_str):
        """Handle the response from the web service now that it came in."""
        try:
            data = json.loads(val)
            if data['responseStatus'] != 200:
                logging.debug("Failed to translate '%s':\n%s", query_str, data['responseDetails'])
                return
            target = data['responseData']['translatedText']
            if not isinstance(target, str):
                raise TypeError('translatedText is %s' % type(target).__name__)
        except (ValueError, KeyError, TypeError) as exc:
            # Not JSON, or of another shape (#4438).
            logging.warning("Ignoring an Apertium translation it can't read: %s", exc)
            return
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
