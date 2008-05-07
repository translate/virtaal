#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2008 Zuza Software Foundation
#
# This file is part of VirTaal
#
# translate is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with translate; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import os
import sys

from virtaal.main_window import VirTaal

PROFILE = True

def module_path():
    """This will get us the program's directory, even if we are frozen using py2exe"""
    if hasattr(sys, "frozen"):
        return os.path.dirname(unicode(sys.executable, sys.getfilesystemencoding()))
    return os.path.dirname(unicode(__file__, sys.getfilesystemencoding( )))

if __name__ == "__main__":
    hwg = VirTaal(module_path())
    if PROFILE:
        import cProfile
        import source_tree_infrastructure.lsprofcalltree as lsprofcalltree
        profiler = cProfile.Profile()
        profiler.run('hwg.run()')
        k_cache_grind = lsprofcalltree.KCacheGrind(profiler)
        f = open('virtaal.kgrind', 'w+')
        k_cache_grind.output(f)
        f.close()
    else:
        hwg.run()

