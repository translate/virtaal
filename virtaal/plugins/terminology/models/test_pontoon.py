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

import io
import os

import configparser

from virtaal.plugins.terminology.models.pontoon import TerminologyModel


class _FakeRequest:
    status = 200

    def __init__(self, headers=b'ETag: "abc123"\r\n'):
        self.result_headers = io.BytesIO(headers)


def test_process_header_config_key_is_a_bare_filename(tmp_path):
    """self.config used to be keyed by an absolute path, which on Windows
    always contains ":" - a char configparser rejects in a key."""
    fake_self = TerminologyModel.__new__(TerminologyModel)
    fake_self.config = {}
    fake_self.matcher = None

    localfile = os.path.join(str(tmp_path), 'en__am.tbx')
    TerminologyModel._process_header(fake_self, _FakeRequest(), b'<tbx/>', localfile=localfile)

    assert list(fake_self.config.keys()) == ['en__am.tbx']
    assert os.path.isfile(localfile)

    # Confirm the key actually survives a real configparser round-trip.
    parser = configparser.ConfigParser()
    parser.add_section('pontoon')
    for key, value in fake_self.config.items():
        parser.set('pontoon', key, value)
    parser.write(io.StringIO())  # raises configparser.InvalidWriteError if broken
