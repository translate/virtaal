---
name: run-virtaal
description: How to launch, identify, and drive a real Virtaal window on macOS for live verification - debug logging, native fullscreen, and targeted screenshots. Load before testing any macOS-specific UI behaviour (menu bar, fullscreen, accelerators) live rather than reasoning from the diff alone. Pairs with the general macos-ui-automation-safety skill, which this doesn't duplicate.
---

# Running Virtaal on macOS

This project's own verification bar requires actually launching the app for
UI-affecting changes, not just running the test suite. This skill covers the
Virtaal-specific mechanics; load `macos-ui-automation-safety` too for the
general rules (unique window titles, real mouse movement vs. clicks, cleanup)
that apply to automating *any* app, not just this one.

A `driver.sh` alongside this file has these as real, sourceable bash
functions - `source .claude/skills/run-virtaal/driver.sh` rather than
retyping the osascript/screencapture incantations each time.

## Launching

```
cd <repo root>
source .venv/bin/activate
python3 bin/virtaal -D <file> > /tmp/virtaal-test.log 2>&1 &
```

- `-D`/`--debug` is required to get `DEBUG`-level output at all - without it
  only `WARNING`+ shows, and in a different format. With it, lines look like
  `DEBUG mainview._on_window_state_event:921: fullscreen: ...` - grep the log
  by module/function name, not just "DEBUG".
- Pass a real file from `devsupport/testfiles/` as the argument - the window
  title becomes `"<filename> - Virtaal"`, giving you the unique title
  `macos-ui-automation-safety` requires. Pick a filename not already open in
  any window you might be sharing the machine with.
- The process shows up in System Events as `"Python"` (unbundled dev-mode
  Python, not a real app bundle) - this is expected and unrelated to any real
  bug; don't mistake it for a branding regression. A real packaged `.app`
  (built via `devsupport/packaging/macos/build_standalone.sh`) shows up under
  its own name instead, if you need to test something specific to that.

## Verifying you have the right window

```
osascript -e 'tell application "System Events"
    return name of every window of process "Python"
end tell'
```
Confirm it returns exactly the one title you expect before doing anything
else - see `macos-ui-automation-safety` for why this check isn't optional.

## Driving native macOS fullscreen

Virtaal hides its own View > Fullscreen menu item on macOS deliberately
(`mainview.py`'s own comment: macOS already provides native fullscreen, and
the app's GDK-level one has no way back to the menu bar). That means the
*only* way to test real fullscreen behaviour is the system's native
mechanism - via the window's `AXFullScreenButton`, not a menu click and not
raw coordinates (the button's on-screen position isn't worth hardcoding):

```applescript
tell application "System Events"
    tell process "Python"
        set frontmost to true
        set win to window "<file> - Virtaal"
        repeat with b in buttons of win
            if (subrole of b) is "AXFullScreenButton" then click b
        end repeat
    end tell
end tell
```

The transition is animated (~0.3-0.5s) - give it a couple of seconds before
checking anything, and expect the AppleScript reference to the pre-fullscreen
window to go stale immediately after (a benign `-1728` error on the *next*
call, not a sign the click failed).

The first click sometimes doesn't register (observed repeatedly - not a
one-off) - check the log for `new=... changed=16` with the `FULLSCREEN` bit
set (`new` value `144`, i.e. `FOCUSED|FULLSCREEN`) before assuming the click
failed outright, and just retry the click if it's not there yet.

Entering fullscreen can also spawn one or two extra small windows titled
`"virtaal"` (generic default title, `AXUnknown` subrole, tiny - GTK tooltip
popups triggered as a side effect of the synthetic interaction, not a real
bug). Match on your specific window's title existing among the results, not
on there being exactly one window.

### Exiting fullscreen

**The `AXFullScreenButton` approach above only works from a windowed state -
once actually fullscreen, that button is not exposed via accessibility at
all** (`buttons of win` returns empty). Escape and the system `Cmd+Ctrl+F`
shortcut (via `System Events keystroke`, scoped or not) also don't reliably
exit it. What does work: hover-reveal the title bar the same way as the menu
bar, then send a **real coordinate click** (down+up, not just an AX action)
on the actual green button (`driver.sh`'s `virtaal_click_at x y`). Don't
hardcode coordinates from this doc or from a past run - hover-reveal first
(`virtaal_move_mouse` to near the top edge, e.g. `(100, 1)`), then take a
small screenshot of the top-left corner (`virtaal_capture_region 0 0 400 60
...`) to see exactly where the traffic lights landed for *your* window size
before clicking. In one confirmed run they landed around `(65, 47)` on a
2560x1440 display - a starting point to visually confirm against, not a
value to reuse blind.

## Revealing the fullscreen menu bar

Hovering the mouse to the top of the screen reveals the menu bar in native
fullscreen - this needs a real `kCGEventMouseMoved`, not a click (see
`macos-ui-automation-safety`). Once in fullscreen, the app covers the entire
display, so a screenshot at this point genuinely only shows Virtaal's own
content - but scope it to the top strip anyway rather than the whole screen,
purely so a screenshot taken a moment too early or late (before/after the
transition) never risks capturing something unrelated:

```
screencapture -x -R 0,0,<screen-width>,120 /path/to/out.png
```

## Cleanup

Kill the PID you launched, delete any scratch screenshots, and uninstall
`pyobjc-framework-Quartz` plus what it pulled in (`pyobjc-core`,
`pyobjc-framework-Cocoa`) from the project's `.venv` if you installed it for
mouse-movement support - don't leave the dev environment with dependencies
that aren't actually part of the project.
