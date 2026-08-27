#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.


import logging
import queue
import threading

from gi.repository import Gtk


def run_in_thread(widget, target, args):
    # Idea from tortoisehg's gtklib.py
    q = queue.Queue()
    def func(*kwargs):
        # An uncaught exception here (e.g. native_widgets.py's
        # win32_open_dialog() hitting a missing pywin32 import) used to
        # just kill this thread silently - q.put() never runs, the
        # caller gets back None indistinguishable from a real "no file
        # chosen" cancel, and nothing is logged anywhere. Confirmed live,
        # 2026-08-23: the symptom is "doesn't crash, dialog just doesn't
        # open". Logging it here doesn't fix whatever the target itself
        # got wrong, but it stops silent failures - see also the guard
        # added to native_widgets._dialog_to_use() for the win32 case
        # specifically.
        try:
            q.put(target(*kwargs))
        except Exception:
            logging.exception("run_in_thread: %r raised", target)

    thread = threading.Thread(target=func, args=args)
    thread.start()

    # we make the given widget insensitive to avoid interaction that we can't
    # handle concurrently
    widget.set_sensitive(False)
    import time
    while thread.is_alive():
        # let gtk process events while target is still running
        Gtk.main_iteration_do(False)
        # Since we are not blocking, we're spinning, which isn't nice. We could
        # set block=True, but then the window might stay insensitive when the
        # thread finished, and only exit this loop when it gets another event
        # (like a mouse move). So we sleep a bit to avoid excessive CPU use.
        time.sleep(0.03)

    widget.set_sensitive(True)
    if q.qsize():
        return q.get(0)
