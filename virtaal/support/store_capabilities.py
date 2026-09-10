#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import io


def can_serialize(trans_store):
    """Whether trans_store.serialize() actually works, checked by
    attempting it into a throwaway buffer rather than hardcoding which
    formats support it - translate-toolkit has no capability flag for
    this, and a hardcoded list would need updating for every current
    and future format that doesn't support writing (currently just
    .qm, but not the only one that ever might)."""
    try:
        trans_store.serialize(io.BytesIO())
        return True
    except NotImplementedError:
        return False
