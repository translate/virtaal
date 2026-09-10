#!/usr/bin/env bash
# shellcheck disable=SC1091  # .venv/bin/activate: not created until `make build`, nothing to follow
# Helper functions for launching/driving/inspecting Virtaal on macOS during
# live verification. See SKILL.md in this same directory for the reasoning
# behind each of these. Source this file rather than running it:
#   source .claude/skills/run-virtaal/driver.sh

# Not derived from $BASH_SOURCE - unreliable when this file is sourced via a
# non-interactive shell (confirmed empty in this exact setup). git itself
# doesn't care where it's invoked from within the repo.
VIRTAAL_REPO="$(git rev-parse --show-toplevel)"

# Launch Virtaal from source with debug logging. Prints the PID.
# Usage: pid=$(virtaal_launch devsupport/testfiles/checks.po /tmp/virtaal.log)
virtaal_launch() {
    local file="$1" logfile="${2:-/tmp/virtaal-driver.log}"
    ( cd "$VIRTAAL_REPO" && source .venv/bin/activate && python3 bin/virtaal -D "$file" ) \
        > "$logfile" 2>&1 &
    echo $!
}

# True (exit 0) if a window with this exact title exists. Doesn't require it
# to be the *only* window - entering fullscreen can spawn small generic
# "virtaal"-titled GTK tooltip popups as a benign side effect.
# Usage: virtaal_verify_window "checks.po - Virtaal"
virtaal_verify_window() {
    local title="$1" names
    names=$(osascript -e '
        tell application "System Events"
            return name of every window of process "Python"
        end tell' 2>/dev/null)
    # Avoids bash arrays/`read -a` - not reliably available in every shell
    # this might be sourced under (confirmed: this exact environment's
    # "bash" rejected `read -ra`, and never populates $BASH_SOURCE either).
    case ",$names," in
        *", $title,"*) return 0 ;;
    esac
    [[ "$names" == "$title" ]]
}

# Click the native macOS fullscreen (green) button via the accessibility API.
# Never Virtaal's own View>Fullscreen menu item - it's hidden on macOS.
# Usage: virtaal_enter_native_fullscreen "checks.po - Virtaal"
virtaal_enter_native_fullscreen() {
    local title="$1"
    osascript -e "
        tell application \"System Events\"
            tell process \"Python\"
                set frontmost to true
                set win to window \"$title\"
                repeat with b in buttons of win
                    if (subrole of b) is \"AXFullScreenButton\" then click b
                end repeat
            end tell
        end tell"
}

# Real mouse movement (not a click) - needed for hover-reveal checks.
# Requires pyobjc-framework-Quartz; see virtaal_install_quartz below.
# Usage: virtaal_move_mouse 1280 1
virtaal_move_mouse() {
    local x="$1" y="$2"
    ( cd "$VIRTAAL_REPO" && source .venv/bin/activate && python3 -c "
import Quartz
e = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, ($x, $y), Quartz.kCGMouseButtonLeft)
Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
" )
}

# Real coordinate click (down+up), not just an AX action - needed to exit
# native fullscreen, since AXFullScreenButton isn't exposed via accessibility
# once already fullscreen. Confirm (x, y) with a screenshot first (see
# virtaal_capture_region) - don't guess blind, it varies by window size.
# Usage: virtaal_click_at 65 47
virtaal_click_at() {
    local x="$1" y="$2"
    ( cd "$VIRTAAL_REPO" && source .venv/bin/activate && python3 -c "
import Quartz, time
for etype in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
    Quartz.CGEventPost(Quartz.kCGHIDEventTap,
        Quartz.CGEventCreateMouseEvent(None, etype, ($x, $y), Quartz.kCGMouseButtonLeft))
    time.sleep(0.05)
" )
}

# Throwaway install/uninstall for virtaal_move_mouse's Quartz dependency -
# always pair install with uninstall once done (see SKILL.md's cleanup note).
virtaal_install_quartz() {
    ( cd "$VIRTAAL_REPO" && source .venv/bin/activate && pip install -q pyobjc-framework-Quartz )
}
virtaal_uninstall_quartz() {
    ( cd "$VIRTAAL_REPO" && source .venv/bin/activate && \
        pip uninstall -y pyobjc-framework-Quartz pyobjc-core pyobjc-framework-Cocoa )
}

# Screenshot a specific region only - see SKILL.md for why not a full-screen
# capture. Usage: virtaal_capture_region 0 0 2560 120 /tmp/out.png
virtaal_capture_region() {
    local x="$1" y="$2" w="$3" h="$4" out="$5"
    screencapture -x -R "$x,$y,$w,$h" "$out"
}

# Kill the launched process. Usage: virtaal_cleanup "$pid"
virtaal_cleanup() {
    kill "$1" 2>/dev/null
}
