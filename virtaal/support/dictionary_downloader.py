#
# Copyright 2026 Zuza Software Foundation
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

"""Downloads a missing spell-check dictionary in the background, via
the app's own async HTTPClient - the non-blocking counterpart to
dictionary_source.py's synchronous download_dictionary() (kept as-is:
simpler, directly testable, still useful standalone).

Reimplements dictionary_source.py's fetch/match orchestration as an
explicit callback chain (tree -> candidate xcu(s) -> files), since
find_dictionary()/download_dictionary() are both written as blocking
loops - one request in flight at a time doesn't fit that shape. The
pure logic (list_dictionary_folders/candidate_folders/
parse_dictionaries_xcu) is reused unchanged.
"""

import json
import logging
import os

from virtaal.support.dictionary_source import (
    RAW_BASE,
    TREE_URL,
    candidate_folders,
    dictionary_write_dir,
    list_dictionary_folders,
    parse_dictionaries_xcu,
)


class DictionaryDownloader:
    """Downloads locale_code's hunspell dictionary in the background,
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
        self._written = []

    def start(self):
        self._client.get(TREE_URL, self._on_tree, error_callback=self._on_error)

    def _on_tree(self, _request, result):
        try:
            tree = json.loads(result.decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as e:
            logging.debug('dictionary download: bad tree response: %s', e)
            return self._give_up()
        folders = list_dictionary_folders(tree)
        candidates = candidate_folders(self.locale_code, folders)
        self._remaining_folders = candidates + [f for f in folders if f not in candidates]
        self._try_next_folder()

    def _try_next_folder(self):
        if not self._remaining_folders:
            return self._give_up()
        self._folder = self._remaining_folders.pop(0)
        url = RAW_BASE + self._folder + '/dictionaries.xcu'
        self._client.get(url, self._on_xcu, error_callback=self._on_xcu_error)

    def _on_xcu_error(self, _request, _status):
        self._try_next_folder()

    def _on_xcu(self, _request, result):
        for entry in parse_dictionaries_xcu(result):
            if self.locale_code in entry['locales']:
                self._files = list(entry['files'])
                return self._fetch_next_file()
        self._try_next_folder()

    def _fetch_next_file(self):
        if not self._files:
            return self._on_success()
        filename = self._files.pop(0)
        url = RAW_BASE + self._folder + '/' + filename
        self._client.get(
            url,
            lambda request, result, fn=filename: self._on_file(fn, result),
            error_callback=lambda request, status, fn=filename: self._on_file_error(fn, status),
        )

    def _on_file(self, filename, result):
        target_dir = self.target_dir or dictionary_write_dir()
        os.makedirs(target_dir, exist_ok=True)
        dest = os.path.join(target_dir, filename)
        with open(dest, 'wb') as f:
            f.write(result)
        self._written.append(dest)
        self._fetch_next_file()

    def _on_file_error(self, filename, status):
        logging.debug('dictionary download: could not get %s/%s: status=%r',
                       self._folder, filename, status)
        for path in self._written:
            os.remove(path)
        self._give_up()

    def _on_success(self):
        logging.debug('Downloaded dictionary for %s', self.locale_code)
        self.on_done()

    def _on_error(self, _request, status):
        logging.debug('dictionary download: request failed, status=%r', status)
        self._give_up()

    def _give_up(self):
        logging.debug('No LibreOffice dictionary found for %s', self.locale_code)
        self.on_done()
