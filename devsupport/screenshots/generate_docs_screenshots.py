#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Generate (or check) docs/screenshots.rst's images.

See issue #3746. Sibling of generate_appdata_screenshots.py (see that
script's own docstring for the --check/--write/--artifact-dir contract,
which this mirrors exactly) - kept as a separate script rather than folded
into it because the two image sets serve different pages, have different
output directories, and grow independently. Both share this directory's
testenv.isolate_home() so neither can touch a real user's Virtaal config.

Unlike the AppData set (three homogeneous "open a file, navigate to a
unit" states), each docs screenshot demonstrates a different feature and
needs its own setup - mode switches, plugin data, synthesized input - so
STATES entries carry a per-state `setup` callable instead of a uniform
tuple shape.
"""

import argparse
import filecmp
import shutil
import sys
import tempfile
from pathlib import Path

from testenv import force_light_theme, isolate_home, park_cursor

isolate_home()

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_STATIC_DIR = REPO_ROOT / "docs" / "_static"
CONTENT = Path(__file__).resolve().parent / "content" / "docs"

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 650


_SELECTED_CHECKS = {"check-printf", "check-endpunc"}


def _setup_checks(app, window, main_controller):
    """Quality Checks: quality-checks.po's unit 3 fails the printf,
    endpunc and brackets checks at once (see that fixture's own header
    comment). Selects printf and endpunc in the mode's own "Select
    Checks" menu, so the button shows real check names instead of the
    generic unfiltered label - demonstrating the actual filter-by-check
    feature, not just that the mode exists."""
    main_controller.open_file(str(CONTENT / "quality-checks.po"))
    yield from _settle(10)
    main_controller.mode_controller.select_mode_by_name("QualityCheck")
    main_controller.store_controller.cursor.force_index(3)
    # Generous: the mode's own checks menu is (re)built once the real
    # checker actually finishes running, not synchronously at mode-
    # select time - toggling checkboxes before that rebuild happens
    # toggles menu items that get thrown away and recreated unchecked.
    yield from _settle(60)

    mode = main_controller.mode_controller.current_mode
    for menuitem, (check_name, _signal_id) in mode._menuitem_checks.items():
        if check_name in _SELECTED_CHECKS:
            menuitem.set_active(True)
    yield from _settle(20)


def _setup_placeable(app, window, main_controller):
    """XML placeable: xml-placeable.po's unit 1 combines a link tag (with
    an attribute) and a bold tag in one string - richer than the single
    <b>...</b> pair the previous hand-captured xml-placeable.png showed."""
    main_controller.open_file(str(CONTENT / "xml-placeable.po"))
    yield from _settle(10)
    main_controller.store_controller.cursor.force_index(1)
    yield from _settle(60)
    # The target's real text cursor otherwise blinks into view at the
    # start of the buffer - not part of the demonstration, and its
    # on/off phase at capture time isn't something this drives.
    unit_view = main_controller.unit_controller.view
    unit_view.targets[0].set_cursor_visible(False)


def _capture_window(gdk_window, width, height):
    """Capture one Gdk.Window and report the device-pixel scale actually
    used, so callers can convert their own logical-unit coordinates.

    Widget coordinates (get_allocation(), translate_coordinates()) are
    always logical units, but the returned pixbuf is in device pixels -
    identical on a 1x display (Xvfb/CI) but not on a HiDPI one (e.g.
    macOS Retina, scale factor 2), where assuming they match silently
    crops to the top-left quarter of the intended region.
    """
    from gi.repository import Gdk

    pixbuf = Gdk.pixbuf_get_from_window(gdk_window, 0, 0, width, height)
    scale = pixbuf.get_width() / width if width else 1
    return pixbuf, scale


def _setup_autocomplete(app, window, main_controller):
    """Autocomplete: autocomplete.po's unit 0 target seeds the word list
    with "vertaalbaar" (see that fixture's own header comment); unit 1's
    target already has valid text typed, so typing "vert" after it shows
    a translator continuing a partial translation, not starting from an
    empty field - triggers a suggested completion to "aalbaar".

    One character at a time, not a bulk insert: AutoCompletor._on_
    insert_text() only reacts to single-character insertions (its own
    guard against reacting to paste-like events), and Gtk.TextBuffer's
    real "insert-text" signal (which TextBox wraps and AutoCompletor
    listens to) fires the same way for a plain insert_at_cursor() as for
    real typing - unlike begin-user-action/end-user-action, which only
    the interactive insert path fires (see the gtk-interactive-insert-
    test-gap skill), this one doesn't need insert_interactive_at_cursor."""
    main_controller.open_file(str(CONTENT / "autocomplete.po"))
    yield from _settle(10)
    main_controller.store_controller.cursor.force_index(1)
    yield from _settle(20)

    target_textbox = main_controller.unit_controller.view.targets[0]
    buffer = target_textbox.buffer
    buffer.place_cursor(buffer.get_end_iter())
    for ch in "vert":
        # A suggestion from the previous character is left selected in
        # the buffer - insert_at_cursor() inserts at the cursor mark
        # regardless, it doesn't replace a selection the way real
        # interactive typing does, so without this the old suggestion
        # stays behind instead of being typed over (observed live, with
        # the previous "trans"/"translatable" fixture: "trans" + a stale
        # "slatable" selection produced "transslatable").
        bounds = buffer.get_selection_bounds()
        if bounds:
            buffer.delete(*bounds)
        buffer.insert_at_cursor(ch)
        yield from _settle(3)
    yield from _settle(20)
    # textbox.suggestion only gets cleared by a real GDK event (a
    # keypress, a focus-out, a click - see textbox.py's own
    # _on_event_remove_suggestion(), wired to exactly those signals),
    # never by insert_at_cursor() alone. Left set, it stuck around on
    # this same (recycled) row widget into the next state's own file -
    # confirmed live: terminology's and TM's target rows both showed a
    # stray "aalbaar" appended, not the fixture's own real content.
    #
    # Setting the public `.suggestion` property (rather than this
    # private attribute) isn't an option here: its setter calls
    # hide_suggestion(), which deletes the still-selected suggestion
    # text from the buffer - exactly right for a real focus-out, but it
    # would erase the very completion this screenshot demonstrates.
    target_textbox._suggestion = None
    target_textbox.refresh_cursor_pos = -1


def _capture_unit_only(main_controller, window):
    """Tight crop around just the active unit row, full window width.

    Padding above only, none below: a few pixels past unit_view's own
    bottom edge isn't blank margin, it's a peek into whatever renders
    right after it. A real stray-render artifact still shows up baked
    into a CI-generated autocomplete.png even with no bottom padding at
    all, so this alone doesn't fully explain it - see issue #3916."""
    width, height = window.get_size()
    pixbuf, scale = _capture_window(window.get_window(), width, height)
    unit_view = main_controller.unit_controller.view
    unit_alloc = unit_view.get_allocation()
    _ux, unit_y = unit_view.translate_coordinates(window, 0, 0)[-2:]
    pad = 10
    top = max(0, unit_y - pad)
    bottom = min(unit_y + unit_alloc.height, height)
    return pixbuf.new_subpixbuf(
        0, round(top * scale), round(width * scale), round((bottom - top) * scale)
    )


def _setup_terminology(app, window, main_controller):
    """Terminology Assistance: terminology.po's unit has one recognised
    term ("Cancel") with two candidate Afrikaans translations in
    terminology.tbx (see that fixture's own header comment), so
    inserting it pops up the completion popup rather than inserting
    a single match directly - real interactive methods throughout
    (insert_placeable), not synthesized key events. The
    target already has a partial translation typed, so the demo shows
    inserting a term mid-sentence, not into an empty field."""
    main_controller.open_file(str(CONTENT / "terminology.po"))
    yield from _settle(10)
    main_controller.store_controller.cursor.force_index(1)
    yield from _settle(20)

    terminology_plugin = main_controller.plugin_controller.plugins["terminology"]
    localfile_model = terminology_plugin.controller.plugin_controller.plugins["localfile"]
    localfile_model.config["files"] = [str(CONTENT / "terminology.tbx")]
    localfile_model.load_files()
    terminology_plugin.controller.rescan_current_unit()
    yield from _settle(20)

    unit_view = main_controller.unit_controller.view
    target_textbox = unit_view.targets[0]
    # The term inserts at the buffer's current cursor position - move it
    # to the end of the already-typed text first, so the demo shows a
    # translator inserting a term mid-sentence, not into an empty field.
    target_textbox.buffer.place_cursor(target_textbox.buffer.get_end_iter())
    unit_view.insert_placeable(target_textbox)
    yield from _settle(30)


def _find_completion_popup(main_controller):
    unit_view = main_controller.unit_controller.view
    popup = unit_view.targets[0].completion_popup
    return popup if popup.is_showing() else None


def _capture_with_popup(main_controller, window, popup_widget):
    """Composite the main window with an open popup widget beside it (a
    completion popup, a suggestions window, ...), then crop to the active
    unit row plus however far the popup extends past it.

    A popup is a real, separate top-level GdkWindow - GTK never renders
    a Gtk.Menu, Gtk.Window(type=POPUP), or similar into the main
    window's own surface, however visually "on top" of it it appears -
    so a plain single-window capture can never see it. Capturing each
    real window separately and compositing them by their actual
    on-screen position is the general fix, reused across every docs
    screenshot state that needs to show a popup (terminology's
    completion popup, TM's suggestions window, ...).

    `popup_widget` may be None (or realized but not visible/mapped, in
    which case its Gdk.Window is None) - some states only sometimes
    have one; the composite then falls back to just the main window.
    """
    import cairo
    from gi.repository import Gdk

    win_width, win_height = window.get_size()
    win_gdk = window.get_window()
    win_pixbuf, scale = _capture_window(win_gdk, win_width, win_height)
    win_x, win_y = win_gdk.get_origin()[-2:]

    # (pixbuf, logical dx, dy relative to the main window's own origin)
    layers = [(win_pixbuf, 0, 0)]
    popup_bottom = 0

    popup_gdk = popup_widget.get_window() if popup_widget is not None else None
    if popup_gdk is not None:
        popup_alloc = popup_widget.get_allocation()
        popup_pixbuf, _popup_scale = _capture_window(
            popup_gdk, popup_alloc.width, popup_alloc.height
        )
        popup_x, popup_y = popup_gdk.get_origin()[-2:]
        dx, dy = popup_x - win_x, popup_y - win_y
        layers.append((popup_pixbuf, dx, dy))
        popup_bottom = dy + popup_alloc.height

    surface = cairo.ImageSurface(
        cairo.FORMAT_ARGB32, round(win_width * scale), round(win_height * scale)
    )
    ctx = cairo.Context(surface)
    for pixbuf, dx, dy in layers:
        Gdk.cairo_set_source_pixbuf(ctx, pixbuf, round(dx * scale), round(dy * scale))
        ctx.paint()
    composite = Gdk.pixbuf_get_from_surface(
        surface, 0, 0, surface.get_width(), surface.get_height()
    )

    unit_view = main_controller.unit_controller.view
    _ux, unit_y = unit_view.translate_coordinates(window, 0, 0)[-2:]
    pad = 10
    top = max(0, unit_y - pad)
    bottom = min(max(popup_bottom, unit_y + unit_view.get_allocation().height) + pad, win_height)
    return composite.new_subpixbuf(
        0, round(top * scale), round(win_width * scale), round((bottom - top) * scale)
    )


def _capture_terminology_combo(main_controller, window):
    """The insertion UI shown alongside the highlighted term - the
    target's completion popup listing the term's translations."""
    return _capture_with_popup(main_controller, window, _find_completion_popup(main_controller))


def _setup_tm(app, window, main_controller):
    """Translation Memory Suggestions: seed the local-TM plugin's own
    throwaway tmserver (auto-launched at startup - see localtm.py) with
    translation-memory-seed.po's two translations via the same
    push_store() call a real save triggers, then open translation-
    memory.po, whose only unit is one word off from each seed unit -
    close enough for two genuine fuzzy (non-100%) matches, not
    identical. Per review: "not really about the TMX file, ... main aim
    is reliable reproduction" - this uses Virtaal's own real ingestion
    path rather than writing to the tmdb sqlite file directly, so it
    can't drift from what the server actually accepts."""
    tm_plugin = main_controller.plugin_controller.plugins["tm"]
    localtm_model = tm_plugin.controller.plugin_controller.plugins["localtm"]

    main_controller.open_file(str(CONTENT / "translation-memory-seed.po"))
    yield from _settle(10)
    localtm_model.push_store(main_controller.store_controller)
    yield from _settle(10)

    main_controller.open_file(str(CONTENT / "translation-memory.po"))
    yield from _settle(10)
    main_controller.store_controller.cursor.force_index(1)
    # Generous: a real HTTP round-trip to the local tmserver, not just a
    # GTK redraw, needs to complete before the suggestions window shows.
    yield from _settle(90)


def _capture_tm_suggestions(main_controller, window):
    """The suggestions window TM matches show in - a real, separate
    Gtk.Window(type=POPUP) (see tmwidgets.TMWindow), same situation as
    the terminology completion popup."""
    tm_plugin = main_controller.plugin_controller.plugins.get("tm")
    tmwindow = tm_plugin.controller.view.tmwindow if tm_plugin else None
    return _capture_with_popup(main_controller, window, tmwindow)


def _capture_mode_and_unit(main_controller, window):
    """Crop from the mode-selection bar (navigation combo + this mode's
    own extra widgets, e.g. QualityCheck's "Select Checks" button) down
    through the active unit row, full window width."""
    width, height = window.get_size()
    pixbuf, scale = _capture_window(window.get_window(), width, height)
    mode_box = main_controller.mode_controller.view.mode_box
    unit_view = main_controller.unit_controller.view
    _mx, mode_y = mode_box.translate_coordinates(window, 0, 0)[-2:]
    _ux, unit_y = unit_view.translate_coordinates(window, 0, 0)[-2:]
    # unit_view's own allocation only covers the source+target textview
    # rows, not the checks status/navigation sidebar beside them (a
    # sibling widget, not a child) - a fixed, generously-sized band below
    # the unit's top edge is simpler and more robust than chasing that
    # sidebar's own widget reference just to union two allocations.
    pad = 20
    band_height = 150
    top = max(0, mode_y - pad)
    bottom = min(unit_y + band_height, height)
    return pixbuf.new_subpixbuf(
        0, round(top * scale), round(width * scale), round((bottom - top) * scale)
    )


# (output filename, setup generator, capture function: (main_controller,
# window) -> Gdk.Pixbuf).
STATES = [
    ("checks.png", _setup_checks, _capture_mode_and_unit),
    ("xml-placeable.png", _setup_placeable, _capture_unit_only),
    # autocomplete deliberately doesn't follow a popup-showing state
    # (terminology/TM) - a stray render artifact in its own capture
    # (issue #3916) may be a carryover from whatever ran immediately
    # before it, not something intrinsic to autocomplete itself.
    ("autocomplete.png", _setup_autocomplete, _capture_unit_only),
    ("terminology-combo.png", _setup_terminology, _capture_terminology_combo),
    ("virtaal-tm.png", _setup_tm, _capture_tm_suggestions),
]
STATE_NAMES = [name for name, *_rest in STATES]


def _settle(frames):
    for _ in range(frames):
        yield


def _run(out_dir):
    """Drive a real Virtaal window through STATES, capturing each to
    out_dir. Runs Gtk.main() - blocks until the driver below quits it."""
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import GLib, Gtk

    from virtaal.common import pan_app
    from virtaal.main import Virtaal

    # See generate_appdata_screenshots.py's identical guard: none of these
    # states demonstrate spellchecking, and gtkspell/enchant fail hard
    # without a dictionary for the active target language.
    pan_app.settings.plugin_state["spellchecker"] = "disabled"
    force_light_theme()

    app = Virtaal("")
    main_controller = app.main_controller
    window = main_controller.view.main_window
    window.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

    def capture(out_path, capture_fn):
        pixbuf = capture_fn(main_controller, window)
        pixbuf.savev(str(out_path), "png", [], [])

    def driver():
        # Give the controllers main.py defers via GLib.idle_add (checks,
        # undo, plugins, ...) a chance to actually construct before the
        # first capture - they only run once Gtk.main() is pumping.
        yield from _settle(10)
        # Needs the window realized (a real GdkWindow, with a real
        # on-screen position) to compute a safe parking spot - not
        # available yet back when Virtaal() was only just constructed.
        park_cursor(window)
        for name, setup, capture_fn in STATES:
            # A state that edits the buffer (e.g. terminology's insert)
            # leaves the store "modified" - the next state's open_file()
            # would otherwise block forever on a real save-confirmation
            # dialog nothing here ever dismisses. These are throwaway
            # demo edits; never save them.
            if main_controller.store_controller.store is not None:
                main_controller.store_controller.set_modified(False)
            # Likewise a mode switch (Quality Checks) - it's a property
            # of the whole app, not the file, so it otherwise leaks into
            # every later state too (observed live: every screenshot
            # after checks.png stayed captioned "Navigation: Quality
            # Checks").
            main_controller.mode_controller.select_default_mode()
            # And the TM suggestions window: tmcontroller.py only ever
            # calls display_matches() (which shows it) when the new
            # unit has real matches - it's never explicitly hidden for
            # a unit with none, so a real match shown for one state can
            # stay stuck on screen into a later, unrelated state.
            tm_plugin = main_controller.plugin_controller.plugins.get("tm")
            if tm_plugin is not None:
                tm_plugin.controller.view.hide()
            yield from setup(app, window, main_controller)
            window.queue_draw()
            yield from _settle(10)
            capture(out_dir / name, capture_fn)
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
        default=DOCS_STATIC_DIR,
        help="where to write images in --write mode (default: docs/_static)",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=REPO_ROOT / "docs-screenshot-artifacts",
        help="in --check mode, where to leave freshly generated images if "
        "they differ, for CI to upload as a build artifact",
    )
    args = parser.parse_args(argv)

    if args.check:
        with tempfile.TemporaryDirectory(prefix="virtaal-docs-screenshots-") as tmp:
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
            mismatches = _compare(tmp_path, DOCS_STATIC_DIR)
            if mismatches:
                if args.artifact_dir.exists():
                    shutil.rmtree(args.artifact_dir)
                shutil.copytree(tmp_path, args.artifact_dir)
                print("Docs screenshots differ from what's committed:", ", ".join(mismatches))
                print(f"Freshly generated images copied to {args.artifact_dir}")
                return 1
            print("Docs screenshots match what's committed.")
            return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _run(args.out_dir)
    print(f"Wrote {len(STATE_NAMES)} screenshots to {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
