#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os
import sys
import textwrap

import pytest

WATCHDOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "devsupport", "testing", "stack_watchdog.py")

spec = importlib.util.spec_from_file_location("stack_watchdog", WATCHDOG)
stack_watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stack_watchdog)

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="no ps or SIGUSR1 on Windows")

# Registers a stack dump the way virtaal/conftest.py does; "parent"
# starts a "child" copy of itself, then each hangs in its own function.
HANGING = textwrap.dedent("""
    import faulthandler, os, signal, subprocess, sys, time
    stacks = open(os.path.join(os.environ["VIRTAAL_STACKS_DIR"], f"{os.getpid()}.txt"), "w")
    faulthandler.register(signal.SIGUSR1, file=stacks, all_threads=True)

    def parent_stuck():
        subprocess.Popen([sys.executable, "-c", sys.argv[2], "child", ""])
        time.sleep(60)

    def child_stuck():
        time.sleep(60)

    parent_stuck() if sys.argv[1] == "parent" else child_stuck()
""")

def test_returns_the_commands_own_exit_code():
    assert stack_watchdog.main(["", "30", "--", sys.executable, "-c", "raise SystemExit(3)"]) == 3


def test_rejects_a_missing_separator(capsys):
    assert stack_watchdog.main(["", "30", sys.executable]) == 2
    assert "stack_watchdog.py <seconds> --" in capsys.readouterr().err


def test_a_hung_process_tree_has_every_stack_dumped_then_is_killed(tmp_path, monkeypatch, capfd):
    monkeypatch.setenv("VIRTAAL_STACKS_DIR", str(tmp_path))

    status = stack_watchdog.main(["", "2", "--", sys.executable, "-c", HANGING, "parent", HANGING])

    out = capfd.readouterr().out
    assert status == stack_watchdog.TIMED_OUT
    assert "still running after 2s" in out
    assert "parent_stuck" in out
    assert "child_stuck" in out
    assert len(list(tmp_path.glob("*.txt"))) == 2
