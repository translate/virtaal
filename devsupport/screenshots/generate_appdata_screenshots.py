#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Generate (or check) Virtaal's AppData/website screenshots.

See issue #3625. Drives a real Virtaal window through a handful of
states and captures each. Full-window states use `xdotool`/`import`
(ImageMagick) when a real X11 session has them, so the window manager's
own decorations (title bar, shadow) are included - Gdk.pixbuf_get_from_
window() can only ever see a window's own client-area content, never
what the WM draws around it, so it's kept only as the portable fallback
(used for the crop states, and for local development on platforms
without those tools, e.g. macOS).

    --check   regenerate into a temp dir and compare against the
              committed images; exits non-zero on any mismatch, writes
              nothing to the repo.
    --write   regenerate straight into --out-dir (default:
              docs/_static/appdata).

Both modes run the exact same generation code, so "does it match" and
"here is the refreshed image" can never drift apart from each other.
"""

import argparse
import atexit
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# This must happen before any virtaal import: pan_app.get_config_dir()
# resolves against $HOME ("~/.virtaal" on Linux, "~/Library/Application
# Support/Virtaal" on macOS), and MainView.quit() would otherwise persist
# this script's capture window size into a real user's Virtaal config.
# Redirecting HOME to a throwaway directory keeps this script from ever
# touching that file - the driver below calls Gtk.main_quit() directly
# instead of main_controller.quit() for the same reason (no save-prompt,
# no settings write).
_fake_home = tempfile.mkdtemp(prefix="virtaal-screenshot-home-")
atexit.register(shutil.rmtree, _fake_home, ignore_errors=True)
os.environ["HOME"] = _fake_home

REPO_ROOT = Path(__file__).resolve().parents[2]
APPDATA_DIR = REPO_ROOT / "docs" / "_static" / "appdata"
TESTFILES = REPO_ROOT / "devsupport" / "testfiles"

# Real Flathub screenshots for apps in this category (GTranslator, Lokalize,
# Parlatype, Bottles) cluster around a ~1.3-1.5 aspect ratio, not the 16:9
# AppStream suggests as a fallback - a multi-pane editor wants a less-wide
# shape. Comfortably under Flathub's 1000x700 cap either way.
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 650

# (output filename, source file to open (None = the literal no-file
# Welcome Screen), unit index to navigate to, whether to crop tight
# around the unit editor instead of keeping the full window).
#
# placeable.png and window.png use frozen excerpts of Virtaal's own real
# Afrikaans/Bengali translations (devsupport/testfiles/{af,bn}-excerpt.po),
# not po/af.po or po/bn_IN.po directly. Earlier versions of this script
# searched those live files at run time for a currently-failing unit -
# real content, but a moving target: a translator fixing the exact bug
# being shown would silently break the demo (or require it to *stay*
# broken to keep working), and a search can surface something that
# technically fails a check but makes a poor example. A hand-picked,
# versioned excerpt keeps the real language and real translator's work
# while staying exactly as stable as the old synthetic fixtures were.
STATES = [
    ("welcome.png", None, None, False),
    # Unit 7: "<b>Original</b>" -> "<b>মূল ভাষা</b>" - a single XML-tag
    # placeable.
    ("placeable.png", TESTFILES / "bn-excerpt.po", 7, True),
    # Unit 6: "Translation reuse (translation memory)" -> "Bestaande
    # vertalings: %(translations)s" - a genuine printf check failure.
    ("window.png", TESTFILES / "af-excerpt.po", 6, False),
]
STATE_NAMES = [name for name, *_rest in STATES]


def _run(out_dir):
    """Drive a real Virtaal window through STATES, capturing each to
    out_dir. Runs Gtk.main() - blocks until the driver below quits it."""
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    from virtaal.common import pan_app
    from virtaal.main import Virtaal

    # None of these states are meant to demonstrate spellchecking, and
    # gtkspell/enchant fail hard (a NULL-speller assertion, repeated on
    # every keystroke-equivalent redraw) whenever the active target
    # language has no dictionary installed on the machine running this.
    # Disabling the plugin up front sidesteps needing a matching
    # dictionary for every fixture's target language.
    pan_app.settings.plugin_state["spellchecker"] = "disabled"

    # Xvfb has no real cursor theme, and (lacking hardware cursor
    # support) draws the pointer by overwriting framebuffer pixels
    # directly - without a theme that's a solid black square, and it
    # showed up baked into every capture at whatever fixed screen
    # position the pointer defaulted to. Parking it off in a corner,
    # once, keeps it away from the window entirely.
    if os.environ.get("DISPLAY") and shutil.which("xdotool"):
        subprocess.run(["xdotool", "mousemove", "2000", "2000"], check=False)

    # The Welcome Screen's "Recent Files" reads Gtk.RecentManager, which
    # starts genuinely empty under the isolated HOME above - pre-populate
    # it so that list isn't blank, with a few different formats for
    # variety (matching the range the hand-captured original showed).
    recent_manager = Gtk.RecentManager.get_default()
    for recent_file in (
        TESTFILES / "workflow.ts",
        TESTFILES / "workflow.xlf",
        REPO_ROOT / "po" / "af.po",
    ):
        recent_manager.add_item(recent_file.as_uri())

    _first_name, first_source, _first_index, _first_crop = STATES[0]
    app = Virtaal(str(first_source) if first_source else "")
    main_controller = app.main_controller
    window = main_controller.view.main_window

    def capture_with_decorations(out_path):
        """Capture via the window manager's own frame (title bar,
        shadow), using xdotool + ImageMagick's `import`. Returns False
        (caller falls back to the plain Gdk capture) when DISPLAY isn't
        a real X11 session or those tools aren't installed - local
        development on macOS, say."""
        if not os.environ.get("DISPLAY"):
            return False
        if not (shutil.which("xdotool") and shutil.which("import")):
            return False
        window.present()
        try:
            window_id = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            subprocess.run(["import", "-window", window_id, str(out_path)], check=True)
        except subprocess.CalledProcessError:
            return False
        return True

    def capture(out_path, crop):
        if not crop and capture_with_decorations(out_path):
            return
        gdk_window = window.get_window()
        width, height = window.get_size()
        pixbuf = Gdk.pixbuf_get_from_window(gdk_window, 0, 0, width, height)
        if crop:
            widget = main_controller.unit_controller.view
            alloc = widget.get_allocation()
            # PyGObject's return arity for this gboolean+out-params call
            # varies by version - (ok, x, y) on some, (x, y) on others.
            # The last two elements are always the coordinates.
            _wx, wy = widget.translate_coordinates(window, 0, 0)[-2:]
            # Full window width (rows always span it), generous vertical
            # padding so a few rows of surrounding context are visible
            # above and below the edited unit, not just the unit itself.
            vpad = 150
            y = max(0, wy - vpad)
            h = min(height - y, alloc.height + 2 * vpad)
            pixbuf = pixbuf.new_subpixbuf(0, y, width, h)
        pixbuf.savev(str(out_path), "png", [], [])

    def driver():
        # Give the controllers main.py defers via GLib.idle_add (checks,
        # undo, plugins, ...) a chance to actually construct before the
        # first capture - they only run once Gtk.main() is pumping.
        for _ in range(10):
            yield
        for i, (name, source, index, crop) in enumerate(STATES):
            if i > 0 and source is not None:
                main_controller.open_file(str(source))
                for _ in range(10):
                    yield
            if index is not None:
                main_controller.store_controller.cursor.force_index(index)
            window.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
            window.queue_draw()
            # Generous: a treeview scroll to the target unit needs time
            # to settle before the crop above reads the right position,
            # not just before the pixels are drawn.
            for _ in range(60):
                yield
            capture(out_dir / name, crop)
        # Not main_controller.quit(): that also persists this capture
        # window's size into settings and prompts to save. Plugins do need
        # an explicit shutdown though - the local-TM plugin's `tmserver`
        # subprocess otherwise outlives us as an orphan holding stdout open.
        if main_controller.plugin_controller:
            main_controller.plugin_controller.shutdown()
        Gtk.main_quit()

    gen = driver()

    def step():
        try:
            next(gen)
        except StopIteration:
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    GLib.timeout_add(150, step)
    app.run()


def _compare(generated_dir, committed_dir):
    mismatches = []
    for name in STATE_NAMES:
        committed_file = committed_dir / name
        if not committed_file.exists() or not filecmp.cmp(
            generated_dir / name, committed_file, shallow=False
        ):
            mismatches.append(name)
    return mismatches


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="regenerate and compare against the committed images; write nothing",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="regenerate and write into --out-dir",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=APPDATA_DIR,
        help="where to write images in --write mode (default: docs/_static/appdata)",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=REPO_ROOT / "screenshot-artifacts",
        help="in --check mode, where to leave freshly generated images if "
        "they differ, for CI to upload as a build artifact",
    )
    args = parser.parse_args(argv)

    if args.check:
        with tempfile.TemporaryDirectory(prefix="virtaal-screenshots-") as tmp:
            tmp_path = Path(tmp)
            try:
                _run(tmp_path)
            except Exception:
                # Exit code 2, not 1: callers (CI) treat 1 as "images
                # differ, harmless drift" and 2 as "the generator itself
                # is broken" - those must stay distinguishable.
                import traceback

                traceback.print_exc()
                return 2
            mismatches = _compare(tmp_path, APPDATA_DIR)
            if mismatches:
                if args.artifact_dir.exists():
                    shutil.rmtree(args.artifact_dir)
                shutil.copytree(tmp_path, args.artifact_dir)
                print("Screenshots differ from what's committed:", ", ".join(mismatches))
                print(f"Freshly generated images copied to {args.artifact_dir}")
                return 1
            print("Screenshots match what's committed.")
            return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _run(args.out_dir)
    print(f"Wrote {len(STATE_NAMES)} screenshots to {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
