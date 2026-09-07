#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

import pytest

from virtaal.common.pan_app import _open_frozen_log


def test_open_frozen_log_survives_characters_a_locale_codepage_cant(tmp_path):
    """Real Windows crash: the frozen build's stdout/stderr log used to
    open with no explicit encoding, defaulting to the system locale's
    codepage (e.g. cp1252) - logging.debug() writing a check-failure
    message containing "≠" (U+2260) raised UnicodeEncodeError from
    inside the logging call itself."""
    message = "Different capitalization ≠ expected\n"

    # Confirm this is a real failure mode, not a hypothetical one - the
    # exact codepage the original crash's own traceback named.
    with pytest.raises(UnicodeEncodeError):
        message.encode('cp1252')

    path = str(tmp_path / "test.log")
    f = _open_frozen_log(path)
    try:
        f.write(message)
    finally:
        f.close()

    with open(path, encoding='utf-8') as f:
        assert message in f.read()
