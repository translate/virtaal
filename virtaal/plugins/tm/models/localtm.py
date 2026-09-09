#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
import os
import socket
import sys

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

        # test if port specified in config is free
        self.config["tmserver_port"] = int(self.config["tmserver_port"])
        if test_port(self.config["tmserver_bind"], self.config["tmserver_port"]):
            port = self.config["tmserver_port"]
        else:
            port = find_free_port(self.config["tmserver_bind"], 49152, 65535)
        # translate-toolkit's own "tmserver" console script (which this used
        # to rely on being on PATH) was removed upstream between releases
        # 3.18.1 and 3.19.0, with no replacement - see virtaal/support/
        # tmserver.py, which vendors it, for the full story. Running it as
        # "-m virtaal.support.tmserver" under our own interpreter needs
        # nothing installed or on PATH, and works the same on Windows and
        # POSIX, so there's no more need for a separate .exe case.
        #
        # A frozen build (PyInstaller) has no separate "python" to hand
        # "-m" to - sys.executable there *is* the bundled app's own
        # compiled launcher, which doesn't understand "-m" at all. bin/
        # virtaal handles a "--run-module <name>" sentinel for exactly this
        # case (dispatches via runpy, same as -m would), gated the same
        # way this branches.
        if platform.is_frozen:
            command = [sys.executable, "--run-module", "virtaal.support.tmserver"]
        else:
            command = [sys.executable, "-m", "virtaal.support.tmserver"]
        command += [
            "-b", self.config["tmserver_bind"],
            "-p", str(port),
            "-d", self.config["tmdb"],
            "--min-similarity=%d" % controller.min_quality,
            "--max-candidates=%d" % controller.max_matches,
        ]

        if pan_app.DEBUG:
            command.append("--debug")

        logging.debug("launching tmserver with command {}".format(" ".join(command)))
        try:
            import subprocess

            from virtaal.support import tmclient

            env = os.environ.copy()
            if not platform.is_frozen:
                # Make sure the subprocess can "import virtaal.support.tmserver"
                # regardless of how *this* process ended up able to (an
                # explicit PYTHONPATH from a source checkout, an editable
                # install, ...) - harmless to add even if it's already on
                # sys.path some other way. Not needed (or meaningful) when
                # frozen - everything's already bundled together.
                import virtaal
                virtaal_parent = os.path.dirname(os.path.dirname(os.path.abspath(virtaal.__file__)))
                existing_path = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = os.pathsep.join(filter(None, [virtaal_parent, existing_path]))

            self.tmserver = subprocess.Popen(command, env=env)
            url = "http://%s:%d/tmserver" % (self.config["tmserver_bind"], port)

            self.tmclient = tmclient.TMClient(url)
        except OSError as e:
            message = "Failed to start TM server: %s" % str(e)
            logging.exception('Failed to start TM server')
            raise

        # Do not use super() here, as remotetm.TMModel does a bit more than we
        # want in this case.
        BaseTMModel.__init__(self, controller)
        self._connect_ids.append((
            self.controller.main_controller.store_controller.connect("store-saved", self.push_store),
            self.controller.main_controller.store_controller
        ))

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
