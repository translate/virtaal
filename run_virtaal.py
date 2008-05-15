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
import logging
from optparse import OptionParser, make_option

from virtaal.main_window import VirTaal
from virtaal import pan_app
from virtaal.pan_app import _

startup_file = None

usage = "usage: %prog [options] [translation_file]"
option_list = [
    make_option("--profile",
                action="store", type="string", dest="profile",
                help=_("Perform profiling, storing the result to the supplied filename.")),
    make_option("--log",
                action="store", type="string", dest="log",
                help=_("Turn on logging, storing the result to the supplied filename")),
    make_option("--no_config",
                action="store_true", dest="no_config", default=False,
                help=_("Do not load the stored configuration. This is mostly useful for testing.")),
]
parser = OptionParser(option_list=option_list, usage=usage)

def module_path():
    """This will get us the program's directory, even if we are frozen using py2exe"""
    if hasattr(sys, "frozen"):
        return os.path.dirname(unicode(sys.executable, sys.getfilesystemencoding()))
    return os.path.dirname(unicode(__file__, sys.getfilesystemencoding( )))

def run_virtaal():
    prog = VirTaal(module_path(), startup_file)
    prog.run()

def profile(profile_file):
    import cProfile
    import source_tree_infrastructure.lsprofcalltree as lsprofcalltree
    logging.info('Staring profiling run')
    profiler = cProfile.Profile()
    profiler.run('run_virtaal()')
    k_cache_grind = lsprofcalltree.KCacheGrind(profiler)
    k_cache_grind.output(profile_file)
    profile_file.close()

def main(args):
    global startup_file
    options, args = parser.parse_args()
    
    if options.log != None:        
        try:
            logging.basicConfig(level=logging.DEBUG,
                                format='%(asctime)s %(levelname)s %(message)s',
                                filename=options.log,
                                filemode='w')
        except IOError:
            parser.error(_("Could not open log file '%s'") % options.log)

    if not options.no_config:
        pan_app.settings.read()

    if len(args) > 1:
        parser.error(_("invalid number of arguments"))
    elif len(args) == 1:
        startup_file = args[0]
 
    if options.profile != None:
        try:
            profile(open(options.profile, 'w+'))                
        except IOError:
            parser.error(_("Could not open profile file '%s'") % options.profile)
    else:
        run_virtaal()

if __name__ == "__main__":    
    main(sys.argv)
