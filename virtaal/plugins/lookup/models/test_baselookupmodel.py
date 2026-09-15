#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.plugins.lookup.models.baselookupmodel import BaseLookupModel


def test_configure_func_is_none_by_default():
    # select_backends() (Select Look-up Services) reads .configure_func
    # off every enabled model, not just ones with something to
    # configure - a real crash (AttributeError) for any model that
    # doesn't set its own, unless the base class declares a default.
    class _MinimalModel(BaseLookupModel):
        def __init__(self):
            pass

    assert _MinimalModel().configure_func is None
