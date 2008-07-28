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
from os import path

from virtaal.main_window import VirTaal
from virtaal import pan_app
from virtaal import __version__

# This has to be a global variable so that cProfile can get access to it 
# (see below in the profiling code).
startup_file = None

usage = _("%prog [options] [translation_file]")
option_list = [
    make_option("--profile",
                action="store", type="string", dest="profile", metavar=_("PROFILE"),
                help=_("Perform profiling, storing the result to the supplied filename.")),
    make_option("--log",
                action="store", type="string", dest="log", metavar=_("LOG"),
                help=_("Turn on logging, storing the result to the supplied filename.")),
    make_option("--config",
                action="store", type="string", dest="config", metavar=_("CONFIG"),
                help=_("Use the configuration file given by the supplied filename.")),
]
parser = OptionParser(option_list=option_list, usage=usage, version=__version__.ver)

def main(argv):
    def set_logging(options):
        if options.log != None:
            try:
                logging.basicConfig(level=logging.DEBUG,
                                    format='%(asctime)s %(levelname)s %(message)s',
                                    filename=path.abspath(options.log),
                                    filemode='w')
            except IOError:
                parser.error(_("Could not open log file '%(filename)s'") % {"filename": options.log})

    def set_config(options):
        try:
            if options.config != None:
                pan_app.settings = pan_app.Settings(path.abspath(options.config))
            pan_app.settings.read()
        except:
            parser.error(_("Could not read configuration file '%(filename)s'") % {"filename": options.config})

    def get_startup_file(options):
        if len(args) > 1:
            parser.error(_("invalid number of arguments"))
        elif len(args) == 1:
            return args[0]
        else:
            return None
  
    def get_virtaal_runner(options):
        def run_virtaal(startup_file):
            prog = VirTaal(startup_file)
            prog.run()

        def profile_runner(startup_file):            
            def profile(profile_file, startup_file):
                import cProfile
                import source_tree_infrastructure.lsprofcalltree as lsprofcalltree
                logging.info('Staring profiling run')
                profiler = cProfile.Profile()
                profiler.runcall(run_virtaal, startup_file)
                k_cache_grind = lsprofcalltree.KCacheGrind(profiler)
                k_cache_grind.output(profile_file)
                profile_file.close()

            try:
                profile(open(options.profile, 'w+'), startup_file)
            except IOError:
                parser.error(_("Could not open profile file '%(filename)s'") % {"filename":options.profile})

        def default_runner(startup_file):
            run_virtaal(startup_file)

        if options.profile != None:
            return profile_runner
        else:
            return default_runner
  
    options, args = parser.parse_args(argv[1:])
    set_logging(options)
    set_config(options)
    startup_file = get_startup_file(options)
    runner = get_virtaal_runner(options)
    runner(startup_file)

if __name__ == "__main__":
    main(sys.argv)
