#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Import pyenchant only if it is really there: a leftover "enchant"
directory with no __init__.py imports as an empty namespace package."""

_USED = ('dict_exists', 'list_languages', 'get_user_config_dir')


def import_enchant():
    """Return the pyenchant module, or None if it isn't usable."""
    try:
        import enchant
    except ImportError:
        return None
    if not all(hasattr(enchant, name) for name in _USED):
        return None
    return enchant
