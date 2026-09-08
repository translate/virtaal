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

import logging

from virtaal.support import statsdb
from virtaal.views.propertiesview import _statistics


def test_statistics_logs_warning_when_state_dict_out_of_sync(monkeypatch, caplog):
    """_statistics()'s consistency check between descriptions and
    statsdb.extended_state_strings used an undefined `logging` name -
    raised NameError instead of the intended warning whenever the two
    tables disagree."""
    monkeypatch.setattr(statsdb, 'extended_state_strings', {0: 'unknown-state'})

    with caplog.at_level(logging.WARNING):
        result = _statistics({})

    assert any("doesn't correspond" in r.message for r in caplog.records)
    assert result == []
