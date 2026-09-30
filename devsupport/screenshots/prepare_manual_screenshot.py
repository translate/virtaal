#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Set up Virtaal for docs/screenshots.rst's manual Windows/macOS
screenshots (issue #3746). Opens content/manual/app-ui.po, wires in its
app-ui.tbx without touching Preferences, navigates to the unit
meant to be captured, and resizes the window to the same size the
Linux-automated screenshots use - then leaves it running for a real,
by-hand capture. This script never takes a screenshot itself: the whole
point of the two remaining images is the real OS's own window-manager
decorations, which only exist around a window on an actual screen.

    python3 devsupport/screenshots/prepare_manual_screenshot.py
"""

import sys
from pathlib import Path

from testenv import force_light_theme, isolate_home, park_cursor

isolate_home()

CONTENT = Path(__file__).resolve().parent / "content" / "manual"

# Same size generate_appdata_screenshots.py and generate_docs_screenshots.py
# use, so every image on the page looks consistent regardless of which OS
# captured it.
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 650

# 0-indexed; see content/manual/app-ui.po's own header comment.
TARGET_UNIT = 9


def main():
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib

    from virtaal.common import pan_app
    from virtaal.main import Virtaal

    pan_app.settings.plugin_state["spellchecker"] = "disabled"
    # Matches the other screenshots' English chrome regardless of the
    # host machine's own system locale - same as bin/virtaal --lang en.
    pan_app.set_ui_language("en")
    force_light_theme()

    app = Virtaal(str(CONTENT / "app-ui.po"))
    main_controller = app.main_controller
    window = main_controller.view.main_window

    def setup():
        # main.py defers building plugin_controller (and friends) via its
        # own GLib.idle_add calls, and plugins themselves load one at a
        # time after that - neither is ready after any fixed delay (worse
        # under emulation, e.g. x64-on-ARM64 Windows), so keep rescheduling
        # until the specific plugin this needs has actually registered.
        if (
            main_controller.plugin_controller is None
            or "terminology" not in main_controller.plugin_controller.plugins
        ):
            return GLib.SOURCE_CONTINUE

        # terminology's own plugin_controller (for its "localfile" model)
        # is built the same lazy, one-at-a-time way - just as unready
        # after any fixed delay as the top-level one above.
        terminology_plugin = main_controller.plugin_controller.plugins["terminology"]
        term_plugin_controller = terminology_plugin.controller.plugin_controller
        if (
            term_plugin_controller is None
            or "localfile" not in term_plugin_controller.plugins
        ):
            return GLib.SOURCE_CONTINUE

        park_cursor(window)
        main_controller.store_controller.cursor.force_index(TARGET_UNIT)
        window.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # Same sequence generate_docs_screenshots.py's _setup_terminology
        # uses - loading via the plugin's own config, not Preferences,
        # so this doesn't depend on any UI navigation to set up.
        localfile_model = term_plugin_controller.plugins["localfile"]
        localfile_model.config["files"] = [str(CONTENT / "app-ui.tbx")]
        localfile_model.load_files()
        terminology_plugin.controller.rescan_current_unit()
        window.queue_draw()

        # The TM suggestions popup computes and renders asynchronously
        # once the unit's selected, not synchronously within this same
        # callback - give it a moment before telling the human it's
        # safe to capture, or the popup won't be showing yet.
        def announce_ready():
            print(
                f"Ready: unit {TARGET_UNIT + 1} selected, window sized to "
                f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}. Capture it with your OS's "
                "own screenshot tool (with window manager decorations), "
                "then close Virtaal."
            )
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(1500, announce_ready)
        return GLib.SOURCE_REMOVE

    GLib.timeout_add(150, setup)
    app.run()


if __name__ == "__main__":
    sys.exit(main())
