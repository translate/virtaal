# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
#
# This file is part of the Translate Toolkit.
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
#
# --- Vendored into Virtaal ---
# Copied verbatim from translate-toolkit (PyPI: translate-toolkit), file
# translate/misc/wsgi.py, at:
#   repo:      https://github.com/translate/translate
#   tag:       3.18.1
#   commit:    315ffec2522f2f2b234f10bed55ce3c2d80fe3da
#   blob sha:  3368c8a1f0bdea22e6a6316e0f989ebbf32c8813
# tmserver.py (and its selector/wsgi helpers, plus tmdb.py) were removed
# from translate-toolkit with no replacement between releases 3.18.1 and
# 3.19.0. The localtm TM plugin's whole point is a zero-config local TM
# server it spawns itself, so this is vendored rather than dropped.
# Nothing below this banner has been altered yet in this commit. See the
# follow-up commit for the Python-3-only / standalone adaptation.

"""Wrapper to launch the bundled CherryPy server."""

import logging

from cheroot.wsgi import Server

logger = logging.getLogger(__name__)


def launch_server(host, port, app, **kwargs) -> None:
    """Use cheroot WSGI server, a multithreaded scallable server."""
    server = Server((host, port), app, **kwargs)
    logger.info("Starting server, listening on port %s", port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
