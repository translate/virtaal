#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""GtkSpell's typelib and library, for the spell checker plugin.
PyInstaller only has hooks for the GI modules it knows about."""

from PyInstaller.utils.hooks.gi import GiModuleInfo


def hook(hook_api):
    module_info = GiModuleInfo('GtkSpell', '3.0')
    if not module_info.available:
        return
    binaries, datas, hiddenimports = module_info.collect_typelib_data()
    hook_api.add_datas(datas)
    hook_api.add_binaries(binaries)
    hook_api.add_imports(*hiddenimports)
