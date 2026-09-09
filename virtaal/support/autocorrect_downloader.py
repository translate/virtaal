#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Downloads a missing autocorrect DocumentList.xml in the background,
via the app's own async HTTPClient - the non-blocking counterpart to
autocorrect_source.py's synchronous download_document_list().

Simpler than DictionaryDownloader: no per-file content check needed
once a folder's guessed (find_document_list_folder() is pure and
already gives a single, definite answer), so this is a two-step chain
(folder listing -> one file), not a fan-out over candidates.
"""

import json
import logging
import os

from virtaal.support.autocorrect_source import (
    CONTENTS_URL,
    RAW_BASE,
    autocorrect_write_dir,
    find_document_list_folder,
    list_autocorrect_folders,
)


class AutocorrectDownloader:
    """Downloads locale_code's autocorrect data in the background,
    calling on_done() (no arguments) once it's either written or given
    up. Silent on failure, same as UpdateChecker: network problems
    must never surface as an application error to the user."""

    def __init__(self, locale_code, on_done=None, client=None, target_dir=None):
        self.locale_code = locale_code.replace('-', '_')
        self.on_done = on_done or (lambda: None)
        self.target_dir = target_dir
        if client is None:
            from virtaal.support.httpclient import HTTPClient
            client = HTTPClient()
            client.set_virtaal_useragent()
        self._client = client

    def start(self):
        self._client.get(CONTENTS_URL, self._on_listing, error_callback=self._on_error)

    def _on_listing(self, _request, result):
        try:
            contents = json.loads(result.decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as e:
            logging.debug('autocorrect download: bad listing response: %s', e)
            return self._give_up()
        folders = list_autocorrect_folders(contents)
        folder = find_document_list_folder(self.locale_code, folders)
        if folder is None:
            return self._give_up()
        url = RAW_BASE + folder + '/DocumentList.xml'
        self._client.get(url, self._on_document_list, error_callback=self._on_error)

    def _on_document_list(self, _request, result):
        target_dir = self.target_dir or autocorrect_write_dir(self.locale_code)
        os.makedirs(target_dir, exist_ok=True)
        dest = os.path.join(target_dir, 'DocumentList.xml')
        with open(dest, 'wb') as f:
            f.write(result)
        logging.debug('Downloaded autocorrect data for %s', self.locale_code)
        self.on_done()

    def _on_error(self, _request, status):
        logging.debug('autocorrect download: request failed, status=%r', status)
        self._give_up()

    def _give_up(self):
        logging.debug('No LibreOffice autocorrect data found for %s', self.locale_code)
        self.on_done()
