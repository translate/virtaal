#!/usr/bin/python

#
#    THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#    THE 'COPYING' FILE FOR DETAILS
#
#    This module is meant for testing and profiling the code only.
#    This file should not be included in any release.
#
#-------------------------------------------------------------------------------

import hotshot
from hotshot import stats

import MainWindow
prog = MainWindow.VirTaal()

profile = hotshot.Profile("Virtaal.profile", lineevents=1)
profile.runcall(prog.run)

s = stats.load("Virtaal.profile")

s.strip_dirs()
s.sort_stats("cumulative", "calls").print_stats()
s.sort_stats("time", "calls").print_stats()

