#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Downloads a missing thesaurus .dat in the background, via the app's
own async HTTPClient - the non-blocking counterpart to
dictionary_source.py's synchronous fetch_dictionary_file().

Unlike DictionaryDownloader/AutocorrectDownloader, there's no discovery
chain here at all: thesaurus.py's own LookupModel always already knows
folder/files before calling start_with_known_files() - either from
asset_manifest.py's cached manifest, or from its own live tree+xcu
check (dictionary_source.fetch_dictionary_tree/fetch_xcu/find_dictionary,
still synchronous, run in its own thread - see thesaurus.py's
docstring). Only the actual file fetch was blocking; that's the one
piece this moves onto the async client. Parsing a fetched .dat stays a
separate, genuinely CPU-bound background thread (thesaurus.py's own
_parse()), unaffected by this.
"""

import logging
import os

from virtaal.common import pan_app
from virtaal.support.dictionary_source import RAW_BASE


class ThesaurusDownloader:
    """Downloads locale_code's thesaurus .dat file(s) in the
    background, calling on_done(success) once they're either written
    or given up. Silent on failure, same as UpdateChecker: network
    problems must never surface as an application error to the user -
    success is passed only so a caller can decide whether to start
    parsing, not to raise anything on failure."""

    def __init__(self, locale_code, on_done=None, client=None, target_dir=None):
        self.locale_code = locale_code.replace('-', '_')
        self.on_done = on_done or (lambda success: None)
        self.target_dir = target_dir
        if client is None:
            from virtaal.support.httpclient import HTTPClient
            client = HTTPClient()
            client.set_virtaal_useragent()
        self._client = client
        self._written = []

    def start_with_known_files(self, folder, files):
        """folder/files already known (from asset_manifest.py's
        manifest, or thesaurus.py's own live check) - straight to
        fetching them, no discovery needed.

        Only .dat files matter (see thesaurus.py's own module
        docstring) - a real folder (fr_FR, for one) has no .idx
        alongside it at all, so any other file is dropped here rather
        than fetched for nothing."""
        self._folder = folder
        self._files = [f for f in files if f.endswith('.dat')]
        if not self._files:
            # Nothing worth fetching at all - distinct from having
            # fetched everything (_fetch_next_file's own empty check,
            # once the loop below has actually run), which is success.
            return self._give_up()
        self._fetch_next_file()

    def _fetch_next_file(self):
        if not self._files:
            return self._on_success()
        filename = self._files.pop(0)
        url = RAW_BASE + self._folder + '/' + filename
        self._client.get(
            url,
            lambda request, result, fn=filename: self._on_file(fn, result),
            error_callback=lambda request, status, fn=filename: self._on_file_error(fn, status),
            download=True,
        )

    def _on_file(self, filename, result):
        try:
            target_dir = self.target_dir or self._default_target_dir()
            os.makedirs(target_dir, exist_ok=True)
            dest = os.path.join(target_dir, filename)
            with open(dest, 'wb') as f:
                f.write(result)
            self._written.append(dest)
        except Exception as e:
            logging.debug('thesaurus download: could not write %s: %s', filename, e)
            return self._on_file_error(filename, None)
        self._fetch_next_file()

    def _on_file_error(self, filename, status):
        logging.debug('thesaurus download: could not get %s/%s: status=%r',
                       self._folder, filename, status)
        for path in self._written:
            os.remove(path)
        self._give_up()

    def _default_target_dir(self):
        # Same path thesaurus.py's own thesaurus_cache_dir() computes -
        # duplicated rather than imported, since thesaurus.py imports
        # this module (ThesaurusDownloader), not the other way round.
        return os.path.join(pan_app.get_config_dir(), 'thesaurus', self.locale_code)

    def _on_success(self):
        logging.debug('Downloaded thesaurus for %s', self.locale_code)
        self.on_done(True)

    def _give_up(self):
        logging.debug('No thesaurus written for %s', self.locale_code)
        self.on_done(False)
