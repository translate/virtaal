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

import logging
import os
import time

from translate.lang.data import normalize_code
from translate.search.match import terminologymatcher
from translate.storage import factory
from translate.storage.base import TranslationStore
from translate.storage.placeables.terminology import TerminologyPlaceable

from virtaal.common import pan_app
from virtaal.support.httpclient import HTTPClient
from .basetermmodel import BaseTerminologyModel

THREE_DAYS = 60 * 60 * 24 * 3


class TerminologyModel(BaseTerminologyModel):
    """A terminology back-end to access community-maintained localization terminology.

        Was originally Translate.org.za's own terminology.locamotion.org,
        a set of static per-language-pair files - now decommissioned.
        Replaced with Mozilla's Pontoon terminology
        (pontoon.mozilla.org/terminology/<locale>.tbx), a live,
        actively-maintained source. Two structural differences from the
        old source that matter here: (1) English-source only - Pontoon's
        terminology has no concept of an arbitrary source language,
        every file is English-to-<locale>, so this model only fetches
        anything when the project's own source language is English;
        other source languages get an empty store, same as before this
        file existed at all. (2) TBX-Basic format (ISO 30042:ed-2, root
        <tbx style="dca" type="TBX-Basic">, <conceptEntry> entries), not
        the older MARTIF-rooted TBX (root <martif>, <termEntry>)
        translate-toolkit's own tbx.py module supports - parsed directly
        in this file (_parse_tbx_basic()) rather than waiting on/
        extending translate-toolkit's own TBX support.
        """

    __gtype_name__ = 'AutoTermTerminology'
    display_name = _('Mozilla Pontoon')
    description = _('Community localization terminology from Mozilla Pontoon')

    # Locale-only (no source language segment) - see class docstring.
    _l10n_URL = 'https://pontoon.mozilla.org/terminology/%(tgtlang)s.tbx'

    TERMDIR = os.path.join(pan_app.get_config_dir(), 'pontoon')

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        super().__init__(controller)
        self.internal_name = internal_name
        self.client = HTTPClient()
        self.client.set_virtaal_useragent()

        self.load_config()

        if not os.path.isdir(self.TERMDIR):
            os.mkdir(self.TERMDIR)

        self.main_controller = controller.main_controller
        self.term_controller = controller
        self.matcher = None
        self.init_matcher()

        lang_controller = self.main_controller.lang_controller
        self.source_lang = lang_controller.source_lang.code
        self.target_lang = lang_controller.target_lang.code
        self._connect_ids.append((
            lang_controller.connect('source-lang-changed', self._on_lang_changed, 'source'),
            lang_controller
        ))
        self._connect_ids.append((
            lang_controller.connect('target-lang-changed', self._on_lang_changed, 'target'),
            lang_controller
        ))

        self.update_terms()

    def init_matcher(self, filename=''):
        """
        Initialize the matcher to be used by the C{TerminologyPlaceable} parser.
        """
        if self.matcher in TerminologyPlaceable.matchers:
            TerminologyPlaceable.matchers.remove(self.matcher)

        if os.path.isfile(filename):
            logging.debug('Loading terminology from %s' % (filename))
            if filename.lower().endswith('.tbx'):
                # Pontoon's export is the TBX-Basic dialect, which
                # translate-toolkit's own tbx.py doesn't parse (it
                # targets the older MARTIF-rooted TBX) - see this
                # class's own docstring. Parsed directly here instead.
                with open(filename, 'rb') as f:
                    self.store = _parse_tbx_basic(f.read())
            else:
                self.store = factory.getobject(filename)
        else:
            logging.debug('Creating empty terminology store')
            self.store = TranslationStore()
        self.store.makeindex()
        self.matcher = terminologymatcher(self.store)
        TerminologyPlaceable.matchers.append(self.matcher)


    # ACCESSORS #
    def _get_curr_term_filename(self, srclang=None, tgtlang=None, ext=None):
        if srclang is None:
            srclang = self.source_lang
        if tgtlang is None:
            tgtlang = self.target_lang
        if not ext:
            # Pontoon only ever serves .tbx - see class docstring. 'po'
            # was the old terminology.locamotion.org source's format.
            ext = 'tbx'

        base = '%s__%s' % (srclang, tgtlang)
        for filename in os.listdir(self.TERMDIR):
            if filename.startswith(base):
                return filename
        return base + os.extsep + ext
    curr_term_filename = property(_get_curr_term_filename)


    # METHODS #
    def update_terms(self, srclang=None, tgtlang=None):
        """Update the terminology file for the given language or all if none specified."""
        if srclang is None:
            srclang = self.source_lang
        if tgtlang is None:
            tgtlang = self.target_lang

        if srclang is None and tgtlang is None:
            # Update all files
            return

        if srclang is None or tgtlang is None:
            raise ValueError('Both srclang and tgtlang must be specified')

        if not _is_english(srclang):
            # Pontoon's terminology is English-source only (see class
            # docstring) - nothing to fetch for any other source
            # language. Same end state as before this source existed:
            # an empty store, no placeable matches, no error.
            logging.debug('Source language %r is not English - Pontoon terminology has nothing to offer, using an empty store' % (srclang,))
            self.init_matcher()
            return

        if not self.is_update_needed(srclang, tgtlang):
            logging.debug('Skipping update for (%s, %s) language pair' % (srclang, tgtlang))
            localfile = self._get_curr_term_filename(srclang, tgtlang)
            localfile = os.path.join(self.TERMDIR, localfile)
            self.init_matcher(localfile)
            return

        self._update_term_file(srclang, tgtlang)

    def is_update_needed(self, srclang, tgtlang):
        localfile = self._get_curr_term_filename(srclang, tgtlang)
        localfile = os.path.join(self.TERMDIR, localfile)
        if not os.path.isfile(localfile):
            return True
        stats = os.stat(localfile)
        from datetime import datetime
        return (time.mktime(datetime.now().timetuple()) - stats.st_mtime) > THREE_DAYS

    def _check_for_update(self, srclang, tgtlang):
        localfile = self._get_curr_term_filename(srclang, tgtlang)
        localfile = os.path.join(self.TERMDIR, localfile)
        etag = None
        if os.path.isfile(localfile) and localfile in self.config:
            etag = self.config[os.path.abspath(localfile)]

        url = self._l10n_URL % {'srclang': srclang, 'tgtlang': tgtlang}

        if not os.path.isfile(localfile):
            localfile = None
        callback = lambda *args: self._process_header(localfile=localfile, *args)

        if logging.root.level != logging.DEBUG:
            self.client.get(url, callback, etag)
        else:
            def error_log(request, result):
                logging.debug('Could not get %s: status %d' % (url, request.status))
            self.client.get(url, callback, etag, error_callback=error_log)

    def _get_ext_from_url(self, url):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        #dir, filename = os.path.split(parsed.path)
        #rewritten for compatibility with Python 2.4:
        dir, filename = os.path.split(parsed[2])
        if not filename or '.' not in filename:
            return None
        ext = filename.split('.')[-1]
        if not ext:
            ext = None
        return ext

    def _get_ext_from_store_guess(self, content):
        # content (from _process_header's result, ultimately
        # httpclient.py's BytesIO().getvalue()) is real bytes, not str -
        # BytesIO, not StringIO. translate.storage.factory's own guess
        # function was also renamed upstream from the misspelled
        # _guessextention to _guess_extension.
        from io import BytesIO
        from translate.storage.factory import _guess_extension
        s = BytesIO(content)
        try:
            return _guess_extension(s)
        except ValueError:
            pass
        return None

    def _process_header(self, request, result, localfile=None):
        if request.status == 304:
            logging.debug('ETag matches for file %s :)' % (localfile))
        elif request.status == 200:
            if not localfile:
                ext = self._get_ext_from_url(request.get_effective_url())
                if ext is None:
                    ext = self._get_ext_from_store_guess(result)
                if ext is None:
                    logging.debug('Unable to determine extension for store. Defaulting to "po".')
                    ext = 'po'
                localfile = self._get_curr_term_filename(ext=ext)
                localfile = os.path.join(self.TERMDIR, localfile)
            logging.debug('Saving to %s' % (localfile))
            # result is real bytes (httpclient.py's BytesIO().getvalue()),
            # not str - 'wb' preserves it exactly regardless of the
            # server's actual charset.
            open(localfile, 'wb').write(result)

            # request.result_headers is httpclient.py's own BytesIO too -
            # .getvalue().splitlines() is a list of bytes lines, so the
            # b'etag:' match and slice both work in bytes; only the
            # stored value itself is decoded to str, since self.config's
            # value ends up formatted into a str header
            # ('If-None-Match: "%s"' % etag) in _check_for_update().
            headers = request.result_headers.getvalue().splitlines()
            etag = ''
            etagline = [l for l in headers if l.lower().startswith(b'etag:')]
            if etagline:
                etag = etagline[0][7:-1].decode('ascii', errors='replace')
            self.config[os.path.abspath(localfile)] = etag
        else:
            logging.debug('Unhandled status code: %d' % (request.status))
            localfile = ''

        if os.path.isfile(localfile):
            # Update mtime
            os.utime(localfile, None)
        self.init_matcher(localfile)

    def _update_term_file(self, srclang, tgtlang):
        """Update the terminology file for the given languages."""
        self.init_matcher() # Make sure that the matcher is empty until we have an update
        filename = self._get_curr_term_filename(srclang, tgtlang)
        localfile = os.path.join(self.TERMDIR, filename)

        self._check_for_update(srclang, tgtlang)


    # SIGNAL HANDLERS #
    def _on_lang_changed(self, lang_controller, lang, which):
        setattr(self, '%s_lang' % (which), lang)
        self.update_terms(self.source_lang, self.target_lang)


def _is_english(langcode):
    """Whether the given language code is some variety of English
        (en, en_US, en-GB, ...) - Pontoon's terminology is English-source
        only, see TerminologyModel's own docstring."""
    normalized = normalize_code(langcode)
    return bool(normalized) and normalized.split('-')[0] == 'en'


# TBX-Basic dialect (ISO 30042:ed-2) namespace - what Pontoon actually
# exports. Distinct from, and structurally incompatible with, the older
# MARTIF-rooted TBX translate-toolkit's own tbx.py module supports (see
# TerminologyModel's own docstring).
_TBX_BASIC_NS = 'urn:iso:std:iso:30042:ed-2'
_XML_NS = 'http://www.w3.org/XML/1998/namespace'


def _parse_tbx_basic(content):
    """Parse a TBX-Basic (ISO 30042:ed-2) document's bytes into a plain
        C{TranslationStore}, one unit per concept entry that has both an
        English source term and a target-language term. Malformed or
        genuinely empty input (e.g. a locale Pontoon has no terminology
        for - a valid header with a completely empty <body>) both just
        produce an empty store, matching this model's existing "nothing
        to show" behaviour rather than raising."""
    store = TranslationStore()
    from lxml import etree
    try:
        root = etree.fromstring(content)
    except etree.Error as e:
        logging.debug('Could not parse TBX-Basic content: %s' % (e,))
        return store

    ns = {'t': _TBX_BASIC_NS, 'xml': _XML_NS}
    for entry in root.findall('.//t:conceptEntry', ns):
        source_term = None
        target_term = None
        for langsec in entry.findall('t:langSec', ns):
            lang = langsec.get('{%s}lang' % (_XML_NS,)) or ''
            term_el = langsec.find('t:termSec/t:term', ns)
            if term_el is None or not term_el.text:
                continue
            if _is_english(lang):
                source_term = term_el.text
            else:
                # First non-English langSec found is the target - a
                # concept entry only ever carries the one target locale
                # that was requested (Pontoon builds the file per
                # locale), so there's nothing to disambiguate between
                # multiple targets here.
                target_term = term_el.text
        if source_term and target_term:
            unit = store.addsourceunit(source_term)
            unit.target = target_term

    return store
