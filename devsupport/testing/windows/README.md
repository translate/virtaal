# Windows testing recipes

Two layers of Windows-side testing exist for Virtaal, covering different
things:

- **CI** (`.github/workflows/ci.yml`'s `build-windows-installer` job)
  builds and UI-tests the raw PyInstaller bundle (`dist\virtaal\
  virtaal.exe`) directly, then packages it into an installer as a final
  step - it never actually *runs* that installer or its uninstaller.
  Good for catching regressions in the app itself on every push, fast.
- **This directory**, run by hand on a real Windows machine (VM or
  physical box), tests the actual install/uninstall/reinstall cycle a
  real user goes through - something CI's bundle-only checks can't
  reach at all. At least one real report ("the unsaved marker seems to
  persist between reinstalls") was specifically about behaviour across
  that cycle.

## Files

- `virtaal_ui_test_helpers.ps1` - drives a running `virtaal.exe`
  (launch, read window geometry/title via Win32, send keystrokes, read
  the frozen build's log files, clean up). Used by both CI and the
  local recipe below.
- `virtaal_install_helpers.ps1` - installs/uninstalls Virtaal's real
  Inno Setup package silently and idempotently, via the Windows
  uninstall registry (works whether the install was per-user or
  machine-wide - doesn't assume a fixed path).
- `Invoke-VirtaalLocalTestPass.ps1` - orchestrates both: uninstall ->
  install -> a battery of UI regression checks against the real
  installed app -> uninstall again, with a pass/fail summary and a
  process exit code.

## Running a local test pass

Windows' default PowerShell execution policy (`Restricted`) blocks
running any local `.ps1` file at all, including this one - if you hit
`... cannot be loaded because running scripts is disabled on this
system`, allow it for just the current window (reverts automatically
when you close it, no permanent/system-wide change):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
```

From the repo root, in PowerShell, on Windows:

```powershell
# Auto-discovers the newest installer under dist\installer or
# dist\Virtaal-windows-installer
.\devsupport\testing\windows\Invoke-VirtaalLocalTestPass.ps1
```

To test a specific installer (e.g. one downloaded from a CI run):

```powershell
gh run download <run-id> -R translate/virtaal -n Virtaal-windows-installer -D dist
.\devsupport\testing\windows\Invoke-VirtaalLocalTestPass.ps1
```

That extracts the `.exe` flat into `dist\` (not into a
`dist\Virtaal-windows-installer\` subfolder, despite the artifact's
name - `gh run download -n <name> -D <dir>` uses `<dir>` as-is, it
doesn't nest by artifact name) - auto-discovery checks a flat
`dist\*.exe` too, alongside `dist\installer\` and
`dist\Virtaal-windows-installer\`, so this just works either way.

Or point at one directly:

```powershell
.\devsupport\testing\windows\Invoke-VirtaalLocalTestPass.ps1 -InstallerPath C:\Downloads\virtaal-1.0.0-beta1-setup.exe
```

Right after installing, the script runs `virtaal.exe --version` and
checks the commit it reports (embedded at build time - see
`virtaal/__version__.py`'s `build_commit`) against this checkout's own
`git rev-parse HEAD`, aborting on a mismatch rather than silently
testing a stale build. Pass `-SkipCommitCheck` to deliberately test a
build that isn't expected to match HEAD (e.g. a specific old release).

Useful switches:

- `-SkipInitialUninstall` - test installing *on top of* whatever's
  already there, instead of starting from a clean slate (the default).
  Use this to specifically test an upgrade path.
- `-KeepInstalled` - leave Virtaal installed afterwards instead of
  tearing back down to a clean slate. Useful when you want to keep
  poking at it by hand right after the automated battery finishes.
- `-HumanDelayMs <n>` - runs at full speed by default; some dialogs
  open and close within a few hundred milliseconds, real but too fast
  to actually watch. `-HumanDelayMs 2000` adds a pause after every
  interaction (keystroke, click, dialog appearing) uniformly, so you
  can follow a run happening live instead of only reading its
  transcript afterward.
- `-RunTest <n,n,...>` - runs only the given check number(s), e.g.
  `-RunTest 18,24`, instead of the full battery. Every check keeps the
  same number it would have in a full run (the counter still advances
  for skipped checks, it just doesn't run their bodies), so a number
  from an earlier transcript or results table always points at the
  same check. For drilling into or validating a fix for one or two
  checks without waiting on a full pass - combine with
  `-SkipInitialUninstall -KeepInstalled` to also skip reinstalling
  between repeats:
  ```powershell
  .\devsupport\testing\windows\Invoke-VirtaalLocalTestPass.ps1 -RunTest 18,24 -SkipInitialUninstall -KeepInstalled
  ```
- `-AppDebugLog` - launches Virtaal with its own `-D`/`--debug` flag and
  relaxes the log-content check to match, so the app's existing
  `logging.debug()`/`logging.info()` calls (mode changes, search match
  counts, which unit a match actually selected, ...) actually show up
  in the transcript instead of being silently discarded (the logging
  module is never configured at all without `-D`). `WARNING`/`ERROR`/
  tracebacks still fail a check exactly as before - this only adds
  tolerance for the expected extra detail. Most useful paired with
  `-RunTest` when a check's pass/fail result makes sense but you need
  to see *why* a specific interaction inside it did or didn't happen:
  ```powershell
  .\devsupport\testing\windows\Invoke-VirtaalLocalTestPass.ps1 -RunTest 18 -AppDebugLog -SkipInitialUninstall -KeepInstalled
  ```

The script exits 0 if every check passed, 1 otherwise - safe to use as
a gate in a self-hosted Windows CI runner later, not just interactively.

Every run's full console output is also written to a transcript under
`.local-test-runs\<timestamp>.log` (gitignored) next to this README -
if this repo checkout is itself a shared folder (e.g. a UTM share from
a macOS host into a Windows VM), that transcript is readable directly
from the host side afterwards without anything needing to be
copy-pasted out of the Windows terminal. The app's own stdout/stderr
logs (`%APPDATA%\Virtaal\std{out,err}_virtaal.log`) and the installer's
log (`%TEMP%\virtaal-install-*.log`) live outside the repo tree and
aren't captured this way on their own - but their content gets printed
to the console (and so into the transcript too) automatically whenever
a check that reads them fails. The click-navigation check also saves
before/after screenshots to the same `.local-test-runs\` directory
regardless of outcome, for the same reason - readable from the host
side without anything needing to be copied out by hand.

### What the battery covers

- App launches cleanly (both with a file argument and from a bare
  welcome screen - genuinely different startup code paths, see
  `virtaal/main.py`'s `_open_with_file` vs `_open_with_welcome`).
- A fresh install shows no modified marker on an untouched file.
- Repeated navigation doesn't grow the window.
- Type + Ctrl+Z clears the modified marker.
- Common shortcuts (Ctrl+Z/X/C/V/O) don't crash.
- Menu navigation (every top-level menu opens/closes cleanly).
- Welcome screen -> a real File > Open dialog (not a CLI argument) ->
  File > Recent Files reopens the same file.
- Ctrl+P opens Preferences and it closes cleanly.
- Ctrl+F's search/filter (`modes/searchmode.py`) doesn't crash.
- F8's quality-checks panel doesn't crash or log an error against a
  file built to exercise several checks.
- Navigation-mode switching (`modes/`) to Incomplete, Quality Checks, and
  Workflow - the "Navigation:" combo's other three modes (`All` and
  `Search` are already covered by other checks) - verified via
  `modecontroller.py`'s own log line that each mode was actually
  reached, not just a screenshot. Doesn't yet verify a mode actually
  narrows the visible unit list, or Workflow's own state-selector popup
  - a real follow-up, not built here.
- Plural-form units (`msgid_plural`) load cleanly, in both an
  nplurals=3 file (`plurals.po`, Polish) and an nplurals=1 file
  (`plurals-zero.po`, Japanese) - genuinely different code paths in
  `unitview.py`'s target-widget layout, not the same case twice.
  Doesn't yet verify the right *number* of target
  textboxes actually renders - needs a human looking at the screenshot.
- Placeable navigation/transfer (Alt+Left/Right/Down) - Alt+Down
  specifically verified to copy source into an empty target.
- Click navigation, and clicking the two status-bar `PopupMenuButton`s
  (check-type/"Project Type" bottom-left, language-pair bottom-right) -
  all three best-effort (see `Send-VirtaalClick`'s own comments for why
  these are inherently a guess without a UI Automation tree available).
- Ctrl+S actually saves and clears the modified marker - verified
  against the file's own on-disk write time, not just the UI marker.
- The real Save/Discard/Cancel dialog (not exercised by any other
  check) appears on a genuine unsaved change, and Discard genuinely
  discards - verified the file's on-disk write time is untouched
  afterward.
- Change file A, discard, open a *different* file B: B shows no
  spurious modified marker - a different, harder-to-hit shape of the
  reopen-modified-flag bug than a same-file reopen.
- A diagnostic (not auto-verified) screenshot of the still-open
  "widgets overlapping on first File>Open" layout glitch, taken at
  the exact moment it would appear.
- Ctrl+C from a clean state doesn't set the modified marker; Ctrl+V
  right after does - Copy/Paste were previously only checked for "don't
  crash", never that they get the modified flag right.
- Alt+Enter opens Properties and closes cleanly (same shape as Ctrl+P).
- F11 fullscreen returns the window to its original size afterward
  (reported live to differ, 2026-08-24 - `_on_fullscreen()` is a plain
  passthrough to GTK's own fullscreen()/unfullscreen(), so this is
  measuring a GTK/GDK Windows-backend quirk, not app code).
- Multi-step undo (two edits, two Ctrl+Z) clears the modified marker -
  the existing single-step check can't distinguish "compares against a
  fixed start" from "correctly walks back an arbitrary number of
  steps".

The three checks above that risk an actual save (Ctrl+S, and anything
that could hit the confirm dialog's default Save button by mistake) all
run against a disposable scratch copy under `%TEMP%\virtaal-test-
scratch\` (`New-VirtaalScratchFile`, cleaned up in Tear down) - never
`po\af.po`/`po\ar.po` directly - so no combination of SendKeys timing,
the wrong dialog response, or a real bug can leave a git-tracked file
modified on disk.

None of this reaches into a check's *content* (e.g. what the checks
panel actually lists, or whether the "right" recent file reopened
beyond its filename appearing in the title) - there's no UI Automation
tree wired up here, just Win32 window geometry/title/foreground-window
plus SendKeys and a plain Win32 mouse click. That's enough to catch
crashes, hangs, and the specific modified-flag/resize regressions this
session was about; deeper content assertions would need a real
Automation-tree library (e.g. FlaUI) wired in as a bigger follow-up.

## Using the pieces separately

Both helper files are meant to be dot-sourced and driven directly too,
e.g. for a quick manual check or a one-off repro:

```powershell
. .\devsupport\testing\windows\virtaal_install_helpers.ps1
. .\devsupport\testing\windows\virtaal_ui_test_helpers.ps1

Uninstall-Virtaal | Out-Null
$install = Install-Virtaal -InstallerPath C:\Downloads\virtaal-1.0.0-beta1-setup.exe
$t = Start-VirtaalTest -ExePath $install.ExePath -Arguments "po\af.po"
Get-VirtaalTitle $t          # e.g. "af.po - Virtaal"
Send-VirtaalKeys $t "x"
Get-VirtaalTitle $t          # e.g. "*af.po - Virtaal"
Send-VirtaalKeys $t "^z"
Get-VirtaalTitle $t          # back to "af.po - Virtaal"
Stop-VirtaalTest $t
Uninstall-Virtaal | Out-Null
```

`Get-VirtaalInstallInfo` (in `virtaal_install_helpers.ps1`) is a
read-only status check - "is Virtaal currently installed, from where,
what version" - with no side effects, useful before deciding whether to
touch anything.

## Future work: macOS and Linux

None of this is reusable on macOS or Linux as-is - it's Windows
technology throughout (Win32 P/Invoke, .NET `SendKeys`, Inno Setup's
install/uninstall mechanics). The *list of what to test* (modified-flag
correctness, undo behaviour, menu/dialog coverage, an install/uninstall
cycle) is portable; the implementation isn't.

- **macOS** already has a parallel, but much more limited: the
  `run-virtaal` skill's `driver.sh` (launch + screenshot verification
  only). Its own notes rule out AppleScript/System Events UI-scripting
  as unreliable on this app (windows/processes it tries to address
  intermittently don't resolve, or report 0 windows for one plainly on
  screen) - there's no macOS equivalent yet of "click a button, type
  text, read a dialog title back". Building one would need real
  Accessibility API driving instead (e.g. via `atomac`/`ApplicationServices`
  directly, not AppleScript's System Events layer).
- **Linux** has no equivalent at all - CI's Linux job runs `pytest`
  under Xvfb (headless unit/GUI tests), not an interactive UI battery.
  Something similar here would need `xdotool`/`wmctrl` for a SendKeys-
  equivalent, or AT-SPI accessibility driving for something closer to
  real UI Automation.

Neither is a small lift - not started, just noted here so it isn't
lost.
