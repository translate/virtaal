#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
import os
import socket

from virtaal.common import pan_app
from virtaal.common.platform import platform

from . import remotetm
from .basetmmodel import BaseTMModel


class TMModel(remotetm.TMModel):
    """This is the translation memory model."""

    __gtype_name__ = 'LocalTMModel'
    display_name = _('Local Translation Memory')
    description = _('Previous translations you have made')
    #l10n: Try to keep this as short as possible.
    shortname = _('Local TM')

    default_config = {
        "tmserver_bind" : "localhost",
        "tmserver_port" : "55555",
        "tmdb" : os.path.join(pan_app.get_config_dir(), "tm.db")
    }

    # INITIALIZERS #
    def __init__(self, internal_name, controller):
        self.internal_name = internal_name
        self.load_config()
        self._check_config()

        port = self._pick_port()
        command = self._build_tmserver_command(port, controller)
        self._launch_tmserver(command, port)

        # Do not use super() here, as remotetm.TMModel does a bit more than we
        # want in this case.
        BaseTMModel.__init__(self, controller)
        self._signal_tracker.connect(self.controller.main_controller.store_controller, "store-saved", self.push_store)

    def _check_config(self):
        """Replace config values the server can't use (#4340)."""
        self.config["tmserver_port"] = pan_app.config_int(
            self.config["tmserver_port"], int(self.default_config["tmserver_port"]), 1, 65535, "tmserver_port")
        # One try here: finding a free port otherwise looks the host up
        # once per port tried, for minutes, and then fails. Resolving
        # isn't enough either: "1.5" is an address, but not this host's.
        host = self.config["tmserver_bind"]
        try:
            if not host.strip():
                raise ValueError("blank")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, 0))
        except (OSError, UnicodeError, ValueError, TypeError) as e:
            default = self.default_config["tmserver_bind"]
            logging.warning("Using %s for tmserver_bind: %r can't be used (%s)", default, host, e)
            self.config["tmserver_bind"] = default
        # Relative to the config folder, not wherever Virtaal was started.
        self.config["tmdb"] = os.path.join(pan_app.get_config_dir(), os.path.expanduser(self.config["tmdb"]))

    def _pick_port(self):
        # test if port specified in config is free
        if test_port(self.config["tmserver_bind"], self.config["tmserver_port"]):
            return self.config["tmserver_port"]
        return find_free_port(self.config["tmserver_bind"], 49152, 65535)

    def _build_tmserver_command(self, port, controller):
        # translate-toolkit's own "tmserver" console script was removed
        # upstream between releases 3.18.1 and 3.19.0 - see
        # virtaal/support/tmserver.py, which vendors it.
        from virtaal.support import helperprocess
        command = helperprocess.command("virtaal.support.tmserver")
        command += [
            "-b", self.config["tmserver_bind"],
            "-p", str(port),
            "-d", self.config["tmdb"],
            "--min-similarity=%d" % controller.min_quality,
            "--max-candidates=%d" % controller.max_matches,
        ]

        if pan_app.DEBUG:
            command.append("--debug")
        return command

    def _launch_tmserver(self, command, port):
        logging.debug("launching tmserver with command {}".format(" ".join(command)))
        try:
            import subprocess

            from virtaal.support import helperprocess, tmclient

            self.tmserver = subprocess.Popen(command, env=helperprocess.env())
            url = "http://%s:%d/tmserver" % (self.config["tmserver_bind"], port)

            self.tmclient = tmclient.TMClient(url)
        except OSError as e:
            message = "Failed to start TM server: %s" % str(e)
            logging.exception('Failed to start TM server')
            raise

    def destroy(self):
        if platform.is_windows:
            import ctypes
            ctypes.windll.kernel32.TerminateProcess(int(self.tmserver._handle), -1)
            logging.debug("killing tmserver with handle %d" % int(self.tmserver._handle))
        else:
            import signal
            os.kill(self.tmserver.pid, signal.SIGTERM)
            logging.debug("killing tmserver with pid %d" % self.tmserver.pid)


def test_port(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False


def find_free_port(host, min_port, max_port):
    import random
    port_range = list(range(min_port, max_port))
    random.shuffle(port_range)
    for port in port_range:
        if test_port(host, port):
            return port
    #FIXME: shall we throw an exception if no free port is found?
    return None
