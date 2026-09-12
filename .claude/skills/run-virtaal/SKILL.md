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

## Sending real keyboard shortcuts

`osascript`'s own process invocation briefly returns focus to whatever
shell/terminal ran it - `set frontmost of process "Python" to true` followed
by a *separate* `osascript` call for the keystroke can silently land the
keystroke back in your own terminal instead (confirmed live: a shortcut
appeared to "not fire" for several rounds until this was caught). Always
combine the frontmost-set and the keystroke in **one** `osascript` invocation,
with a short `delay` between them:

```applescript
tell application "System Events"
    set frontmost of process "Python" to true
    delay 0.3
    keystroke "o" using command down
end tell
```

If the user is also active on the same machine, their own focus changes can
race with this the same way - don't automate keystrokes while someone else
might be using the machine concurrently (see `macos-ui-automation-safety`).

## Navigating into nested UI (Preferences, tabs, per-row buttons)

**Preferences lives under the "Python" app menu, not Edit** - macOS's
native menu bar puts it where `mainview.py`'s `osxapp.insert_app_menu_item`
moved it, labelled "Settings…" (the system's own standard relabelling of
"Preferences…"), not under Virtaal's own Edit menu:

```applescript
tell application "System Events"
    tell process "Python"
        click menu bar item "Python" of menu bar 1
        delay 0.4
        click menu item "Settings…" of menu 1 of menu bar item "Python" of menu bar 1
    end tell
end tell
```

**GTK's own internal widgets (notebook tabs, per-row buttons inside a
TreeView) are mostly invisible to the accessibility tree** - `entire
contents of window "Virtaal Preferences"` returns almost nothing below the
window's own chrome buttons, so `click button "Plug-ins" of ...` fails with
"Invalid index" or "Can't get...". Two fallbacks, both confirmed working:

- **Keyboard navigation** for things like notebook tabs - focus the window,
  then send arrow-key codes directly (`key code 124` is Right, `123` Left):
  ```
  tell application "System Events"
      set frontmost of process "Python" to true
      key code 124
      key code 124
  end tell
  ```
  (two Right-arrows moves General -> Placeables -> Plug-ins).
- **Real coordinate clicks** via `click at {x, y}` (a direct System Events
  command, not an AX action) when there's no keyboard path. Coordinates are
  in the same **point** units as `position`/`size of window` - NOT the pixel
  units a screenshot uses. A screenshot is 2x on Retina, so convert: `sips -g
  pixelWidth -g pixelHeight file.png` against the window's own `size` gives
  the real scale factor; divide the pixel coordinates you read off the image
  by that factor before adding the window's `position` offset.

**A row's inline button (e.g. a plugin's "Configure..." in the Plug-ins
list) only exists as a real, clickable widget once that row is in GTK's
*editing* state** - `CellRendererWidget.do_render()` only paints a text
layout (name + description) for the normal, non-editing row; the actual
embedded `Gtk.Button` is part of the widget `do_start_editing()` builds and
shows, which only happens once the row is selected. Clicking (or
arrow-keying to) the row first is required before its button is reachable
at all - and get the row's own y-coordinate right, since a click a row or
two off just silently selects/edits the wrong plugin.

A stray, empty, tiny window can appear right after a synthetic click or
keystroke (no title, no content) - same benign tooltip-popup artifact noted
under fullscreen above, not a sign the action failed.

## Inspecting a native menu item's real key equivalent

Don't infer whether a shortcut works from the menu's visible label alone -
query the actual accessibility attributes, and separately confirm the
keypress really dispatches (a label can be correct while the underlying
`Gtk.AccelMap`/`GtkosxApplication` wiring still doesn't fire, or vice versa -
both have been observed independently):

```applescript
tell application "System Events"
    tell process "Python"
        set fileMenu to menu 1 of menu bar item "File" of menu bar 1
        repeat with mi in menu items of fileMenu
            try
                log {name of mi, value of attribute "AXMenuItemCmdChar" of mi, value of attribute "AXMenuItemCmdModifiers" of mi}
            end try
        end repeat
    end tell
end tell
```

`AXMenuItemCmdModifiers` of `0` means Command alone; nonzero values add
Shift/Option/Control - a character that itself needs Shift to type (like
`?`) can show a nonzero value without that being a bug. A missing
`AXMenuItemCmdChar` means no key equivalent is assigned at all, regardless of
what `Gtk.AccelMap`/`accel_path` claims.

## Testing settings persistence without touching real config

`bin/virtaal --config <path>` points at an isolated `.ini` file instead of
the real `~/Library/Application Support/Virtaal/virtaal.ini` - use this for
anything that reads/writes settings (window size/position, recent files,
etc.) so a test run can never corrupt or race with the user's own config,
especially if they might launch their own instance concurrently.

## Cleanup

**Killing the PID you launched does not kill its `tmserver` child** -
the local TM plugin spawns `python3 -m virtaal.support.tmserver` as a
separate process, which survives its parent being killed and keeps
running indefinitely (confirmed directly: 30+ of these accumulated
silently across one session's worth of test launches, each holding a
real local port). **`pkill -f "virtaal.support.tmserver"` is too broad** -
it matches every tmserver on the machine by command-line substring,
including ones from a session you didn't start (confirmed live: it killed
a pre-existing, unrelated tmserver that had been running since before this
session began). Find and kill only the one your own launch spawned:

```
ps aux | grep "[v]irtaal.support.tmserver"   # note the PID and port
kill <that PID>
kill <the bin/virtaal PID you launched>
```

Check for leftovers before assuming a session is clean: `ps aux | grep
-i "[P]ython.*virtaal"`.

Also delete any scratch screenshots, and uninstall
`pyobjc-framework-Quartz` plus what it pulled in (`pyobjc-core`,
`pyobjc-framework-Cocoa`) from the project's `.venv` if you installed it for
mouse-movement support - don't leave the dev environment with dependencies
that aren't actually part of the project.
