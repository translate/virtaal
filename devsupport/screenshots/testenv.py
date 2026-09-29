#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Shared setup for this directory's generate_*_screenshots.py drivers."""

import atexit
import os
import shutil
import subprocess
import tempfile


def isolate_home():
    """Redirect $HOME to a throwaway directory.

    Must be called before any `virtaal` import: pan_app.get_config_dir()
    resolves against $HOME ("~/.virtaal" on Linux, "~/Library/Application
    Support/Virtaal" on macOS), and MainView.quit() would otherwise persist
    a capture window's size into a real user's Virtaal config. Callers
    should call Gtk.main_quit() directly instead of main_controller.quit()
    for the same reason (no save-prompt, no settings write).
    """
    fake_home = tempfile.mkdtemp(prefix="virtaal-screenshot-home-")
    atexit.register(shutil.rmtree, fake_home, ignore_errors=True)
    os.environ["HOME"] = fake_home


def force_light_theme():
    """Force light theme regardless of the host's own OS-level dark-mode
    setting, so a screenshot looks the same run to run.

    A plain Gtk.Settings property set isn't enough on macOS/Windows:
    mainview.py polls the real OS setting every 2s (#3842) and will flip
    gtk-application-prefer-dark-theme right back to whatever the host
    actually prefers - a real risk on any dev machine with system dark
    mode on, not just a theoretical one. Patching the two OS detectors
    to always report light avoids that fight; Linux has no such
    polling; call before constructing the Virtaal app.
    """
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    from virtaal.views.mainview import MainView

    MainView._detect_macos_is_dark = lambda self: False
    MainView._detect_windows_is_dark = lambda self: False
    Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", False)


def park_cursor(window):
    """Move the mouse pointer clear of `window`, on a real X11 session.

    Xvfb has no real cursor theme, and (lacking hardware cursor support)
    draws the pointer by overwriting framebuffer pixels directly -
    without a theme that's a solid black square, baked directly into
    any capture whose crop happens to include wherever the pointer
    defaults to. A fixed, arbitrarily-large coordinate (e.g. 2000, 2000)
    isn't safe against this: xdotool clamps it to the Xvfb screen's own
    (much smaller, e.g. 1024x768) bounds, which can still land inside
    the window depending on where the window manager placed it - seen
    live in a CI-generated autocomplete.png. Placing it just outside
    the window's own real, current bounds is what actually works. A
    no-op if DISPLAY isn't a real X11 session or xdotool isn't
    installed (e.g. local development on macOS).
    """
    if not (os.environ.get("DISPLAY") and shutil.which("xdotool")):
        return
    from gi.repository import Gdk

    gdk_window = window.get_window()
    win_x, win_y = gdk_window.get_origin()[-2:]
    win_width, _win_height = window.get_size()
    screen_width = Gdk.Screen.get_default().get_width()
    target_x = win_x + win_width + 50
    if target_x >= screen_width:
        target_x = max(win_x - 50, 0)
    subprocess.run(["xdotool", "mousemove", str(target_x), str(win_y)], check=False)
