#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.common import GObjectWrapper


class BaseController(GObjectWrapper):
    """Interface for controllers."""

    def __init__(self):
        raise NotImplementedError('This interface cannot be instantiated.')
