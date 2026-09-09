#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from .basetmmodel import BaseTMModel


class TMModel(BaseTMModel):
    """This is a dummy (testing) translation memory model."""

    __gtype_name__ = 'DummyTMModel'
    display_name = _('Dummy TM provider for testing')
    description = _('A translation memory suggestion providers that is only useful for testing')

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        super().__init__(controller)


    # METHODS #
    def query(self, tmcontroller, unit):
        query_str = unit.source
        tm_matches = []
        tm_matches.append({
            'source': 'This match has no "quality" field',
            'target': 'Hierdie woordeboek het geen "quality"-veld nie.',
            'tmsource': 'DummyTM'
        })
        tm_matches.append({
            'source': query_str.lower(),
            'target': query_str.upper(),
            'quality': 100,
            'tmsource': 'DummyTM'
        })
        reverse_str = list(query_str)
        reverse_str.reverse()
        reverse_str = ''.join(reverse_str)
        tm_matches.append({
            'source': reverse_str.lower(),
            'target': reverse_str.upper(),
            'quality': 32,
            'tmsource': 'DummyTM'
        })

        self.emit('match-found', query_str, tm_matches)
