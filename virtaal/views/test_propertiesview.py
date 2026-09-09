#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

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
