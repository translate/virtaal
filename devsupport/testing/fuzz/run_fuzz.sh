#!/bin/sh
# Runs fuzz_ui.py with each Virtaal process under whichever native
# debugger is available, so a crash leaves a real backtrace in the
# results instead of just "the process died".
#
# Usage: devsupport/testing/fuzz/run_fuzz.sh [fuzz_ui.py arguments]
#   devsupport/testing/fuzz/run_fuzz.sh --duration-seconds 1200
#
# Exit code is fuzz_ui.py's: 1 for a new failure or a stale known-bug entry.

set -eu
# shellcheck disable=SC1007  # deliberate: CDPATH= scoped to this one cd
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

PYTHON=${PYTHON:-python3}

if command -v gdb >/dev/null 2>&1; then
    exec "$PYTHON" "$script_dir/fuzz_ui.py" --debugger gdb "$@"
elif command -v lldb >/dev/null 2>&1; then
    exec "$PYTHON" "$script_dir/fuzz_ui.py" --debugger lldb "$@"
else
    echo "No gdb/lldb found - crashes get only faulthandler's Python-level trace"
    exec "$PYTHON" "$script_dir/fuzz_ui.py" "$@"
fi
