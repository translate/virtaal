#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Overrides pyinstaller-hooks-contrib's own hook-enchant.py, which
collects the entire pyenchant wheel's data (all bundled dictionaries)
unconditionally via collect_data_files('enchant') - undermining
virtaal.spec's own deliberate dictionary filtering regardless of it,
since PyInstaller merges every hook's contributions. hookspath puts
this file ahead of the contributed one. Binaries (the actual enchant
backend DLLs) still need collecting; data doesn't - virtaal.spec's
own datas loop already adds exactly the dictionaries wanted."""

from PyInstaller.utils.hooks import collect_dynamic_libs

binaries = collect_dynamic_libs('enchant')
datas = []
excludedimports = ['enchant.tests']
