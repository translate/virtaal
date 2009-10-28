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
import os
import StringIO
import sys
import time
from datetime import datetime
from translate.search.match import terminologymatcher
from translate.storage import factory
from translate.storage.base import TranslationStore, TranslationUnit
from translate.storage.placeables.terminology import TerminologyPlaceable

from virtaal.__version__ import ver as version
from virtaal.common import pan_app
from virtaal.support.httpclient import HTTPClient, HTTPRequest

from basetermmodel import BaseTerminologyModel

THREE_DAYS = 60 * 60 * 24 * 3


class AutoTermClient(HTTPClient):
    """
    REST client to handle the communication between Virtaal and the terminology-
    providing web server.
    """

    def __init__(self):
        super(AutoTermClient, self).__init__()
        platform = sys.platform
        if platform.startswith('linux'):
            if os.path.isfile('/etc/lsb-release'):
                try:
                    lines = open('/etc/lsb-release').read().splitlines()
                    for line in lines:
                        if line.startswith('DISTRIB_DESCRIPTION'):
                            distro = line.split('=')[-1]
                            distro = distro.replace('"', '')
                            platform = '%s; %s' % (platform, distro)
                except Exception:
                    pass
        self.user_agent = 'Virtaal/%s (%s)' % (version, platform)

    def get(self, url, callback, etag=None, error_callback=None):
        headers = None
        if etag:
            # See http://en.wikipedia.org/wiki/HTTP_ETag for more details about ETags
            headers = ['If-None-Match: "%s"' % (etag)]
        request = HTTPRequest(url, '', headers=headers, user_agent=self.user_agent, follow_location=True)
        self.add(request)

        if callback:
            request.connect('http-success', callback)
            request.connect('http-redirect', callback)
        if error_callback:
            request.connect('http-client-error', error_callback)
            request.connect('http-server-error', error_callback)


class TerminologyModel(BaseTerminologyModel):
    """A terminology back-end to access the Translate.org.za-managed terminology."""

    __gtype_name__ = 'AutoTermTerminology'
    display_name = _('AutoTerm')
    description = _('Provides self-managed terminology from Translate.org.za.')

    default_config = {
        'last_update': 0,
        'url': 'http://terminology.locamotion.org/%(srclang)s/%(tgtlang)s',
    }

    TERMDIR = os.path.join(pan_app.get_config_dir(), 'autoterm')

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        super(TerminologyModel, self).__init__(controller)
        self.internal_name = internal_name
        self.client = AutoTermClient()

        self.load_config()
        self.config['last_update'] = float(self.config['last_update'])

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
            self.store = factory.getobject(filename)
        else:
            self.store = TranslationStore()
        self.store.makeindex()
        self.matcher = terminologymatcher(self.store)
        TerminologyPlaceable.matchers.append(self.matcher)


    # ACCESSORS #
    def _get_curr_term_filename(self, srclang=None, tgtlang=None):
        if srclang is None:
            srclang = self.source_lang
        if tgtlang is None:
            tgtlang = self.target_lang

        base = '%s__%s' % (srclang, tgtlang)
        for filename in os.listdir(self.TERMDIR):
            if filename.startswith(base):
                return filename
        return base + '.po'
    curr_term_filname = property(_get_curr_term_filename)


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

        self._update_term_file(srclang, tgtlang)
        self.config['last_update'] = time.mktime(datetime.now().timetuple())

    def is_update_needed(self, srclang, tgtlang):
        localfile = self._get_curr_term_filename(srclang, tgtlang)
        if not os.path.isfile(localfile):
            return True
        stats = os.stat(localfile)
        return (time.mktime(datetime.now().timetuple()) - stats.st_mtime) > THREE_DAYS

    def _check_for_update(self, srclang, tgtlang):
        localfile = self._get_curr_term_filename(srclang, tgtlang)
        localfile = os.path.join(self.TERMDIR, localfile)
        etag = None
        if os.path.isfile(localfile) and localfile in self.config:
            etag = self.config[os.path.abspath(localfile)]
        url = self.config['url'] % {'srclang': srclang, 'tgtlang': tgtlang}
        callback = lambda *args: self._process_header(localfile=localfile, *args)
        if logging.root.level != logging.DEBUG:
            self.client.get(url, callback, etag)
        else:
            def error_log(request, result):
                logging.debug('Could not get %s: status %d' % (url, request.status))
            self.client.get(url, callback, etag, error_callback=error_log)

    def _process_header(self, request, result, localfile=None):
        if request.status == 304:
            logging.debug('ETag matches for file %s :)' % (localfile))
        elif request.status == 200:
            logging.debug('File received')
            if not localfile:
                localfile = self.curr_term_filname
                logging.debug('Not sure where to save new terminology file.')
            logging.debug('Saving to %s' % (localfile))
            open(localfile, 'w').write(result)

            # Find ETag header and save the value
            headers = request.result_headers.getvalue().splitlines()
            etag = ''
            etagline = [l for l in headers if l.lower().startswith('etag:')]
            if etagline:
                etag = etagline[0][7:-1]
            self.config[os.path.abspath(localfile)] = etag
        else:
            logging.debug('Unhandled status code: %d' % (request.status))
            return

        if os.path.isfile(localfile):
            # Update mtime
            os.utime(localfile, None)
        self.init_matcher(localfile)

    def _update_term_file(self, srclang, tgtlang):
        """Update the terminology file for the given languages."""
        filename = self._get_curr_term_filename(srclang, tgtlang)
        localfile = os.path.join(self.TERMDIR, filename)

        self._check_for_update(srclang, tgtlang)


    # SIGNAL HANDLERS #
    def _on_lang_changed(self, lang_controller, lang, which):
        setattr(self, '%s_lang' % (which), lang)
        self.update_terms(self.source_lang, self.target_lang)
