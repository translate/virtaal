#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import io
import os

from virtaal.plugins.terminology.models.autoterm import TerminologyModel

GOOD_PO = b'''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr "Bonjour"
'''

# A captive-portal/signon page: served with a normal 200 status, but
# not the terminology file it claims to be.
SIGNON_PAGE = b'<html><body>Please log in to continue</body></html>'


class _FakeRequest:
    status = 200

    def __init__(self, headers=b'ETag: "abc123"\r\n'):
        self.result_headers = io.BytesIO(headers)


def _fake_self():
    fake_self = TerminologyModel.__new__(TerminologyModel)
    fake_self.config = {}
    fake_self.matcher = None
    return fake_self


def test_process_header_saves_a_parseable_response(tmp_path):
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')

    TerminologyModel._process_header(fake_self, _FakeRequest(), GOOD_PO, localfile=localfile)

    assert os.path.isfile(localfile)
    assert open(localfile, 'rb').read() == GOOD_PO


def test_process_header_discards_an_unparseable_response(tmp_path):
    # #1503: a signon network's login page used to get saved and
    # cached as if it were the real terminology file.
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')

    TerminologyModel._process_header(fake_self, _FakeRequest(), SIGNON_PAGE, localfile=localfile)

    assert not os.path.isfile(localfile)
    assert fake_self.config == {}


def test_process_header_keeps_a_previously_cached_file_on_bad_response(tmp_path):
    fake_self = _fake_self()
    localfile = os.path.join(str(tmp_path), 'en__fr.po')
    open(localfile, 'wb').write(GOOD_PO)

    TerminologyModel._process_header(fake_self, _FakeRequest(), SIGNON_PAGE, localfile=localfile)

    assert open(localfile, 'rb').read() == GOOD_PO
