#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 Zuza Software Foundation
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

"""In-process UI fuzzer - see FEATURE-CRASH-HARDENING.md for the design this
implements.

Drives Virtaal's real controllers through varied, randomised interaction
(navigate, switch mode, edit, undo, save, close/reopen, resize) well beyond
what the pytest suite exercises, to shake out more instances of Release
Blocker #8's pattern (a live GTK object graph torn down in a way that isn't
safe against Python's own garbage collection) before a release does, not
just the one instance already root-caused and fixed there.

A found crash is a real native crash (the process dies, non-zero/negative
exit code) - this script can't catch that itself, only leave behind enough
of a trail (a flushed-per-action log, plus faulthandler) to diagnose it
afterwards. Run it under gdb/lldb (see run_fuzz.sh) for a full backtrace.

Usage:
    python devsupport/testing/fuzz/fuzz_ui.py [--iterations N] [--seed N]
        [--duration-seconds N] [--log PATH]

Exit code 0 means it ran the requested iterations/duration without dying -
not proof of no bugs, just no *native crash* in this run. Python-level
exceptions raised by an action are caught, logged, and don't stop the run,
since the goal is coverage of what happens *next*, not a clean stack trace
for those (pytest's own suite is the place for behavioural correctness).
"""

import argparse
import faulthandler
import os
import random
import sys
import tempfile
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, REPO_ROOT)

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from virtaal.common import pan_app
from virtaal.controllers.maincontroller import MainController
from virtaal.controllers.storecontroller import StoreController
from virtaal.controllers.unitcontroller import UnitController
from virtaal.controllers.undocontroller import UndoController
from virtaal.controllers.modecontroller import ModeController
from virtaal.controllers.checkscontroller import ChecksController
from virtaal.controllers.langcontroller import LanguageController

TESTFILES_DIR = os.path.join(REPO_ROOT, 'devsupport', 'testfiles')
DEFAULT_TESTFILES = ['workflow.po', 'workflow.xliff', 'workflow.ts', 'checks.po']

# Deliberately excluded for now, see FEATURE-CRASH-HARDENING.md: toggling
# spellcheck/TM requires main_controller.load_plugins(), which does real
# network downloads and spawns a tmserver subprocess - too slow/flaky for
# a tight fuzz loop. A plugin-aware fuzzer is a real, separate follow-up.


class Fuzzer:
    def __init__(self, seed, log_path, testfiles_dir=TESTFILES_DIR):
        self.rng = random.Random(seed)
        self.testfiles = [
            os.path.join(testfiles_dir, name) for name in DEFAULT_TESTFILES
            if os.path.exists(os.path.join(testfiles_dir, name))
        ]
        if not self.testfiles:
            raise RuntimeError('No test fixtures found under %s' % (testfiles_dir))

        self._log_file = open(log_path, 'a', buffering=1)
        self._tempdir = tempfile.mkdtemp(prefix='virtaal-fuzz-')
        self.iteration = 0

        # Avoids StoreModel._update_header()'s modal save-time prompt.
        pan_app.settings.translator['name'] = 'Fuzzer'
        pan_app.settings.translator['email'] = 'fuzzer@example.com'
        pan_app.settings.translator['team'] = 'none'

        self._build_controllers()
        self.store_controller.open_file(self.rng.choice(self.testfiles))
        self._load_current_unit()

        # weight, name, action
        self.actions = [
            (30, 'navigate', self._act_navigate),
            (15, 'switch_mode', self._act_switch_mode),
            (15, 'edit_target', self._act_edit_target),
            (10, 'undo', self._act_undo),
            (10, 'save_temp', self._act_save_temp),
            (10, 'close_reopen', self._act_close_reopen),
            (10, 'resize_window', self._act_resize_window),
        ]

    def _build_controllers(self):
        # Same construction order as virtaal/test/test_scaffolding.py -
        # a real, working controller hierarchy, minus pytest.
        self.main_controller = MainController()
        self.store_controller = StoreController(self.main_controller)
        self.unit_controller = UnitController(self.store_controller)
        self.undo_controller = UndoController(self.main_controller)
        self.mode_controller = ModeController(self.main_controller)
        self.checks_controller = ChecksController(self.main_controller)
        self.lang_controller = LanguageController(self.main_controller)

    def log(self, message):
        timestamp = time.strftime('%H:%M:%S')
        line = '%s [%d] %s' % (timestamp, self.iteration, message)
        print(line)
        self._log_file.write(line + '\n')
        self._log_file.flush()

    # ACTIONS #
    # Each just calls the same real controller methods a user action
    # (menu click, keyboard shortcut, navigation click) would end up
    # calling - see each mode/controller's own view code for the real
    # call site this mirrors.

    def _load_current_unit(self):
        # Real navigation loads the newly-selected unit for editing via
        # the treeview's cell renderer (get_unit_celleditor() ->
        # UnitController.load_unit()) - without a real treeview widget
        # rendering anything, nothing else does this, so edit_target/
        # save_temp would otherwise always find no unit loaded.
        cursor = self.store_controller.cursor
        unit = cursor and cursor.deref()
        if unit is not None:
            self.store_controller.get_unit_celleditor(unit)

    def _act_navigate(self):
        cursor = self.store_controller.cursor
        if cursor is None:
            return
        offset = self.rng.choice([-100, -5, -1, 1, 5, 100])
        cursor.move(offset)
        self._load_current_unit()

    def _act_switch_mode(self):
        name = self.rng.choice(list(self.mode_controller.modes.keys()))
        self.mode_controller.select_mode_by_name(name)

    def _act_edit_target(self):
        unit = self.store_controller.cursor and self.store_controller.cursor.deref()
        if unit is None:
            return
        text = 'fuzz-%d-%s' % (self.iteration, self.rng.choice(['a', 'ab\tcd', '', '<x>y</x>', u'ünïcödé']))
        self.unit_controller.set_unit_target(0, text)

    def _act_undo(self):
        self.undo_controller.mnu_undo.activate()

    def _act_save_temp(self):
        if self.store_controller.store is None:
            return
        ext = os.path.splitext(self.store_controller.get_store_filename() or '.po')[1] or '.po'
        path = os.path.join(self._tempdir, 'fuzz-save-%d%s' % (self.iteration, ext))
        self.store_controller.save_file(path)

    def _act_close_reopen(self):
        self.store_controller.close_file()
        self.store_controller.open_file(self.rng.choice(self.testfiles))
        self._load_current_unit()

    def _act_resize_window(self):
        window = self.main_controller.view.main_window
        window.resize(self.rng.randint(300, 1200), self.rng.randint(200, 900))

    # RUN LOOP #

    def step(self):
        self.iteration += 1
        total_weight = sum(weight for weight, _, _ in self.actions)
        pick = self.rng.uniform(0, total_weight)
        upto = 0
        for weight, name, action in self.actions:
            upto += weight
            if pick <= upto:
                self.log(name)
                try:
                    action()
                except Exception as exc:
                    # A Python-level exception, not a crash - log and
                    # keep going, we're after native crashes here.
                    self.log('  exception (non-fatal): %r' % (exc,))
                break

        # Pump the real GTK main loop so anything the action deferred
        # (GLib.idle_add/timeout_add, signal emission) actually runs
        # before the next action - the same interleaving a real user
        # session has, and exactly the kind of timing Release Blocker
        # #8 depended on.
        while Gtk.events_pending():
            Gtk.main_iteration()

    def run(self, iterations=None, duration_seconds=None):
        self.log('fuzz run starting: seed reproduces this exact sequence')
        start = time.monotonic()
        count = 0
        while True:
            if iterations is not None and count >= iterations:
                break
            if duration_seconds is not None and time.monotonic() - start >= duration_seconds:
                break
            self.step()
            count += 1
        self.log('fuzz run completed %d iterations without a native crash' % (count))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--iterations', type=int, default=500,
                         help='Number of actions to perform (default: 500). Ignored if --duration-seconds is given.')
    parser.add_argument('--duration-seconds', type=int, default=None,
                         help='Run for this long instead of a fixed iteration count (for scheduled CI runs).')
    parser.add_argument('--seed', type=int, default=None,
                         help='RNG seed - printed at the start of every run so a crash can be replayed exactly.')
    parser.add_argument('--log', default=None,
                         help='Path to append the action log to (default: a temp file, path printed at startup).')
    parser.add_argument('--watchdog-seconds', type=int, default=None,
                         help='Force-exit with a full stack dump if still running after this long '
                              '(default: 2x --duration-seconds, or 1800 for a fixed --iterations run) - '
                              'catches a step() that never returns instead of hanging the CI job for hours.')
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**32)
    log_path = args.log or os.path.join(tempfile.gettempdir(), 'virtaal-fuzz-%d.log' % (seed))

    faulthandler.enable()
    watchdog_seconds = args.watchdog_seconds
    if watchdog_seconds is None:
        watchdog_seconds = args.duration_seconds * 2 if args.duration_seconds else 1800
    faulthandler.dump_traceback_later(watchdog_seconds, exit=True)
    print('seed=%d log=%s watchdog_seconds=%d' % (seed, log_path, watchdog_seconds))

    fuzzer = Fuzzer(seed=seed, log_path=log_path)
    fuzzer.run(iterations=None if args.duration_seconds else args.iterations,
               duration_seconds=args.duration_seconds)


if __name__ == '__main__':
    main()
