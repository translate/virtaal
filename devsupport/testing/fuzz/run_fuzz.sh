#!/bin/sh
# Runs fuzz_ui.py under whichever native debugger is available, so a crash
# leaves behind a real backtrace instead of just "the process died" - see
# FEATURE-CRASH-HARDENING.md's "Crash capture" section.
#
# Usage: devsupport/testing/fuzz/run_fuzz.sh [fuzz_ui.py arguments]
#   devsupport/testing/fuzz/run_fuzz.sh --duration-seconds 1200
#
# Exit code is fuzz_ui.py's own real exit status (0 = completed without a
# native crash; 128+signal, e.g. 139, for a crash) - neither gdb nor lldb
# propagate the inferior's exit code as their own by default, so both
# branches below extract it explicitly rather than trusting $?.

set -eu
# shellcheck disable=SC1007  # deliberate: CDPATH= scoped to this one cd
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
fuzz_script="$script_dir/fuzz_ui.py"

PYTHON=${PYTHON:-python3}

if command -v gdb >/dev/null 2>&1; then
    echo "Running under gdb (Linux crash capture)"
    # $_exitcode is only set after a normal exit - stays void (and the
    # "if" below false) if the inferior is still stopped on a fatal
    # signal instead, in which case "thread apply all bt full" is the
    # useful output and we exit 1 ourselves.
    exec gdb -q --batch \
        -ex run \
        -ex "thread apply all bt full" \
        -ex "if \$_exitcode >= 0" \
        -ex "  quit \$_exitcode" \
        -ex "end" \
        -ex "quit 1" \
        --args "$PYTHON" "$fuzz_script" "$@"
elif command -v lldb >/dev/null 2>&1; then
    echo "Running under lldb (macOS crash capture)"
    # --one-line-on-crash: only fires if the target actually stops on a
    # signal, unlike gdb's approach above - lldb's batch mode otherwise
    # halts the command queue on any unexpected stop (see the Release
    # Blocker #8 investigation for why "bt" alone after "continue"
    # silently produces nothing).
    #
    # lldb's own exit code reflects whether *lldb* ran cleanly, not the
    # inferior's exit status - "Process N exited with status = C" is
    # only ever printed to its output, so pull the real status from
    # there instead of trusting $?. No such line at all means the
    # inferior is still stopped on a real crash signal (the "bt all"
    # above already captured it) - treat that as a failure.
    output=$(mktemp)
    lldb -b \
        -k "bt all" \
        -k "quit" \
        -o "process launch" \
        -o "continue" \
        -- "$PYTHON" "$fuzz_script" "$@" 2>&1 | tee "$output"
    status_line=$(grep -o 'exited with status = [0-9]*' "$output" | tail -1)
    rm -f "$output"
    if [ -n "$status_line" ]; then
        exit "${status_line##* }"
    fi
    exit 1
else
    echo "No gdb/lldb found - running plain (relies on faulthandler for any Python-level trace)"
    exec "$PYTHON" "$fuzz_script" "$@"
fi
