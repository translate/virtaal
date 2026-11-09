#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Makes gi.repository.GtkSpell a runtime module, so its hook runs:
PyInstaller treats GI modules it has no hooks for as missing."""


def pre_safe_import_module(api):
    api.add_runtime_module(api.module_name)
