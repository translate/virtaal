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

# We should ideally be obtaining a list from them, or use their API to see if
# something is supported.
_languages = {
  'af': 'Afrikaans',
  'sq': 'Albanian',
  'am': 'Amharic',
  'ar': 'Arabic',
  'hy': 'Armenian',
  'az': 'Azerbaijani',
  'eu': 'Basque',
  'be': 'Belarusian',
  'bn': 'Bengali',
  'bh': 'Bihari',
  'bg': 'Bulgarian',
  'my': 'Burmese',
  'ca': 'Catalan',
  'chr': 'Cherokee',
  'zh': 'Chinese',
  'zh-CN': 'Chinese_simplified',
  'zh-TW': 'Chinese_traditional',
  'hr': 'Croatian',
  'cs': 'Czech',
  'da': 'Danish',
  'dv': 'Dhivehi',
  'nl': 'Dutch',
  'en': 'English',
  'eo': 'Esperanto',
  'et': 'Estonian',
  'tl': 'Filipino',
  'fi': 'Finnish',
  'fr': 'French',
  'gl': 'Galician',
  'ka': 'Georgian',
  'de': 'German',
  'el': 'Greek',
  'gn': 'Guarani',
  'gu': 'Gujarati',
  'iw': 'Hebrew',
  'hi': 'Hindi',
  'hu': 'Hungarian',
  'is': 'Icelandic',
  'id': 'Indonesian',
  'iu': 'Inuktitut',
  'ga': 'Irish',
  'it': 'Italian',
  'ja': 'Japanese',
  'kn': 'Kannada',
  'kk': 'Kazakh',
  'km': 'Khmer',
  'ko': 'Korean',
  'ku': 'Kurdish',
  'ky': 'Kyrgyz',
  'lo': 'Laothian',
  'lv': 'Latvian',
  'lt': 'Lithuanian',
  'mk': 'Macedonian',
  'ms': 'Malay',
  'ml': 'Malayalam',
  'mt': 'Maltese',
  'mr': 'Marathi',
  'mn': 'Mongolian',
  'ne': 'Nepali',
  'no': 'Norwegian',
  'or': 'Oriya',
  'ps': 'Pashto',
  'fa': 'Persian',
  'pl': 'Polish',
  'pt-PT': 'Portuguese',
  'pa': 'Punjabi',
  'ro': 'Romanian',
  'ru': 'Russian',
  'sa': 'Sanskrit',
  'sr': 'Serbian',
  'sd': 'Sindhi',
  'si': 'Sinhalese',
  'sk': 'Slovak',
  'sl': 'Slovenian',
  'es': 'Spanish',
  'sw': 'Swahili',
  'sv': 'Swedish',
  'tg': 'Tajik',
  'ta': 'Tamil',
  'tl': 'Tagalog',
  'te': 'Telugu',
  'th': 'Thai',
  'bo': 'Tibetan',
  'tr': 'Turkish',
  'uk': 'Ukrainian',
  'ur': 'Urdu',
  'uz': 'Uzbek',
  'ug': 'Uighur',
  'vi': 'Vietnamese',
  'cy': 'Welsh',
  'yi': 'Yiddish'
};

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
        super(TMModel, self).__init__(controller)
        self.client = HTTPClient()

    # METHODS #
    def query(self, tmcontroller, query_str):
        if self.source_lang not in _languages or self.target_lang not in _languages:
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
