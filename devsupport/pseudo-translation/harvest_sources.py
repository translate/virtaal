#!/usr/bin/env python3
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Drives a real Virtaal window under the pseudo-source locale and
records every piece of UI text it can find, with the catalog its tag
names (vt:, gtk:, glib:, spell:, mac:, iso:) or none.

Shows the suggestions window with a match from each TM source that's on
by default, selects each mode and opens its menu, and opens the
terminology and look-up source lists.
Opens the text boxes' context menus, including the spelling menu on a
misspelled word, then activates every menu item in turn (except Quit),
opening each dialog it leads to. After each step it walks every
toplevel window - widgets, menus and submenus, tooltips, combo entries,
column titles, window titles and accelerator labels. A dialog's run() returns Cancel at once
instead of blocking; native file choosers and links don't open.

Writes JSON: {"strings": [{"text", "screen", "widget", "shown", ...}, ...]}.
"shown" is false for text in a hidden widget, e.g. a dialog built ahead
of being opened; "tooltip" is true for a tooltip's text. See resolve_sources.py for mapping the tagged strings
back to msgids.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "devsupport" / "screenshots"))
sys.path.insert(0, str(REPO_ROOT))

from testenv import force_light_theme, isolate_home  # noqa: E402

isolate_home()

FIXTURE = REPO_ROOT / "devsupport" / "screenshots" / "content" / "docs" / "quality-checks.po"
# Run last: they replace or close the open file.
LAST_ITEMS = ("mnu_tutorial", "mnu_close")
SKIP_ITEMS = ("mnu_quit",)
# Online sources make runs depend on the network; local TM, current file
# and local terminology stay.
OFFLINE_PLUGINS = """\
[tm]
disabled_models = _dummytm,remotetm,apertium,google_translate,moses,amagama
[terminology]
disabled_models = autoterm,pontoon
"""
MARKUP_RE = re.compile(r"<[^>]+>")


class Harvest:
    def __init__(self):
        self.strings = []
        self.seen = set()

    def add(self, text, screen, widget, within, window="", shown=True, tooltip=False):
        if not text or not text.strip():
            return
        text = MARKUP_RE.sub("", text) if "<" in text else text
        key = (text, screen, shown, tooltip)
        if key not in self.seen:
            self.seen.add(key)
            record = {"text": text, "screen": screen, "widget": type(widget).__name__,
                      "within": within, "window": window, "shown": shown}
            if tooltip:
                record["tooltip"] = True
            self.strings.append(record)

    def walk(self, widget, screen, visited, within="", window="", shown=True):
        """within: the nearest enclosing GTK-built composite that matters
            for where a string comes from, e.g. "FileChooser" (only shown on
            Linux - Windows and macOS use the OS's own dialog).
            shown: whether every widget above this one is visible. A
            submenu counts as shown when its menu item is."""
        from gi.repository import Gtk

        from virtaal.views.widgets.selectview import SelectView
        # Keyed by id() but holding the widget: a PyGObject wrapper from
        # forall() is temporary, and once collected its id() can be
        # reused by another widget's, which would then be skipped.
        if id(widget) in visited:
            return
        visited[id(widget)] = widget
        for composite in (Gtk.FileChooser, Gtk.FontButton, Gtk.AboutDialog, Gtk.ShortcutsWindow, Gtk.Menu):
            if isinstance(widget, composite):
                within = composite.__name__
        if isinstance(widget, Gtk.Window) and not window:
            window = "%s %r" % (type(widget).__name__, widget.get_title())
        shown = shown and (widget.get_visible() or isinstance(widget, Gtk.Menu))
        add = lambda text, tooltip=False: self.add(text, screen, widget, within, window, shown, tooltip)  # noqa: E731

        if isinstance(widget, Gtk.Window):
            add(widget.get_title())
        if isinstance(widget, Gtk.Label):
            add(widget.get_label())
        if isinstance(widget, Gtk.MenuItem) and widget.get_accel_path():
            # Its shortcut as the menu shows it, e.g. "Ctrl+S" - GTK's own
            # keyboard labels, except with macOS's symbols.
            found, key = Gtk.AccelMap.lookup_entry(widget.get_accel_path())
            if found and key.accel_key:
                add(Gtk.accelerator_get_label(key.accel_key, key.accel_mods))
        add(widget.get_tooltip_text(), tooltip=True)
        if isinstance(widget, Gtk.Entry):
            add(widget.get_placeholder_text())
        if isinstance(widget, Gtk.TreeView):
            for column in widget.get_columns():
                add(column.get_title())
            if widget.get_tooltip_column() >= 0 and widget.get_model() is not None:
                for row in widget.get_model():
                    add(row[widget.get_tooltip_column()], tooltip=True)
        if isinstance(widget, SelectView) and widget.get_model() is not None:
            # Each row's name and description, drawn by a cell renderer.
            for row in widget.get_model():
                add(row[1])
                add(row[2])
        if isinstance(widget, Gtk.ComboBox) and widget.get_model() is not None:
            for row in widget.get_model():
                for value in row:
                    if isinstance(value, str):
                        add(value)
        if isinstance(widget, Gtk.ShortcutsShortcut):
            add(widget.get_property("title"))
        if isinstance(widget, Gtk.ShortcutsGroup):
            add(widget.get_property("title"))
        if isinstance(widget, Gtk.MenuItem) and widget.get_submenu() is not None:
            self.walk(widget.get_submenu(), screen, visited, within, window, shown)
        for attached in Gtk.Menu.get_for_attach_widget(widget):
            self.walk(attached, screen, visited, within, window, shown and attached.get_visible())
        if isinstance(widget, Gtk.Container):
            children = []
            widget.forall(children.append)
            for child in children:
                self.walk(child, screen, visited, within, window, shown)

    def walk_toplevels(self, screen, extra=()):
        """extra: widgets outside any toplevel, e.g. the menu bar macOS's
            native menu integration takes out of the main window."""
        from gi.repository import Gtk
        # Visible windows first: a menu reached through its item counts as
        # shown, but not through the hidden popup window that also holds it.
        toplevels = Gtk.Window.list_toplevels()
        visited = {}
        for widget in ([w for w in toplevels if w.get_visible()] + list(extra)
                       + [w for w in toplevels if not w.get_visible()]):
            self.walk(widget, screen, visited)


def _collect(widget, cls, out):
    """Every widget of class cls in widget's tree, including internal
    children."""
    from gi.repository import Gtk
    if isinstance(widget, cls):
        out.append(widget)
    if isinstance(widget, Gtk.Container):
        children = []
        widget.forall(children.append)
        for child in children:
            _collect(child, cls, out)


def _leaf_menu_items(menubar):
    from gi.repository import Gtk
    items = []

    def visit(menu):
        for item in menu.get_children():
            if not isinstance(item, Gtk.MenuItem) or isinstance(item, Gtk.SeparatorMenuItem):
                continue
            if item.get_submenu() is not None:
                visit(item.get_submenu())
            else:
                items.append(item)

    visit(menubar)
    return items


def _stub_blocking_calls(harvest, current_screen):
    """Dialogs record themselves and return Cancel instead of blocking;
    native file choosers and links do nothing."""
    from gi.repository import Gtk

    from virtaal.support import openmailto

    def run_dialog(dialog):
        dialog.show_all()
        screen = current_screen[0] + " > " + (dialog.get_title() or type(dialog).__name__)
        harvest.walk(dialog, screen, {})
        # A font button's font chooser is GTK's own on every platform.
        font_buttons = []
        _collect(dialog, Gtk.FontButton, font_buttons)
        if font_buttons:
            font_buttons[0].clicked()
            for chooser in Gtk.Window.list_toplevels():
                if isinstance(chooser, Gtk.FontChooserDialog):
                    harvest.walk(chooser, screen + " > font chooser", {})
                    chooser.hide()
        dialog.hide()
        return Gtk.ResponseType.CANCEL

    Gtk.Dialog.run = run_dialog
    Gtk.NativeDialog.run = lambda dialog: Gtk.ResponseType.CANCEL
    Gtk.NativeDialog.show = lambda dialog: None
    openmailto.open = lambda *args, **kwargs: None


def _set_pseudo_source():
    from virtaal import cli
    options = argparse.Namespace(pseudo_translation=False, pseudo_translation_bidi=False,
                                 pseudo_translation_source=True)
    cli._set_pseudo_translation(options, argparse.ArgumentParser())


def run(output):
    _set_pseudo_source()
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    from virtaal.common import pan_app
    from virtaal.main import Virtaal

    pan_app.settings.plugin_state["spellchecker"] = "enabled"
    with open(os.path.join(pan_app.get_config_dir(), "plugins.ini"), "w", encoding="utf-8") as f:
        f.write(OFFLINE_PLUGINS)
    force_light_theme()

    workdir = tempfile.mkdtemp(prefix="virtaal-harvest-")
    testfile = os.path.join(workdir, FIXTURE.name)
    shutil.copy(FIXTURE, testfile)

    harvest = Harvest()
    current_screen = ["startup"]
    _stub_blocking_calls(harvest, current_screen)

    app = Virtaal("")
    main_controller = app.main_controller
    main_window = main_controller.view.main_window

    def settle(frames=6):
        for _ in range(frames):
            yield

    def visit(screen):
        current_screen[0] = screen
        harvest.walk_toplevels(screen, extra=[main_controller.view.gui.get_object("menubar")])

    def open_subdialogs(screen):
        """Open the About dialog's credits page, if it was just shown."""
        for window in Gtk.Window.list_toplevels():
            if not (isinstance(window, Gtk.AboutDialog) and window.get_visible()):
                continue
            buttons = []
            _collect(window, Gtk.ToggleButton, buttons)
            for button in buttons:
                if (button.get_label() or "").endswith("C_redits"):
                    button.set_active(True)
                    yield from settle(3)
                    visit(screen + " > credits")
                    button.set_active(False)

    def driver():
        yield from settle(10)
        visit("welcome screen")
        main_controller.open_file(testfile)
        yield from settle()
        visit("file open")

        # The suggestions window, fed one fixed match per TM source that's
        # on by default, so no TM is needed. A source's name is drawn by a
        # cell renderer, so it's recorded here.
        tm = main_controller.plugin_controller.plugins.get("tm")
        unit = main_controller.unit_controller.current_unit
        if tm and tm.controller.plugin_controller.plugins and unit is not None:
            backends = tm.controller.plugin_controller
            off = tm.default_config["disabled_models"].split(",") + ["basetmmodel"]
            sources = [backends.get_plugin_info(name)["display_name"]
                       for name in backends._find_plugin_names() if name not in off]
            tm.controller.send_tm_query(unit)
            query = tm.controller.current_query
            tm.controller.accept_response(next(iter(backends.plugins.values())), query, [
                {"source": query, "target": "Harvest match %d" % i, "quality": 90 - i, "tmsource": source}
                for i, source in enumerate(sources)])
            tm.controller.view.show(force=True)
            yield from settle()
            visit("tm suggestions")
            tmwindow = tm.controller.view.tmwindow
            for row in tmwindow.liststore:
                harvest.add(row[0]["tmsource"], "tm suggestions", tmwindow.treeview, "",
                            "%s %r" % (type(tmwindow).__name__, tmwindow.get_title()))
            tm.controller.view.hide()

        mode_controller = main_controller.mode_controller
        for name, mode in sorted(mode_controller.modes.items()):
            if mode.is_available():
                mode_controller.select_mode(mode)
                yield from settle()
                visit("mode %s" % name)
                if hasattr(mode, "btn_popup"):
                    mode.btn_popup.popup()
                    yield from settle(3)
                    visit("mode %s menu" % name)
                    mode.btn_popup.menu.popdown()
        mode_controller.select_default_mode()
        yield from settle()

        # Every terminology and look-up source, enabled or not.
        for name in ("terminology", "lookup"):
            plugin = main_controller.plugin_controller.plugins.get(name)
            if plugin:
                current_screen[0] = "%s sources" % name
                plugin.controller.view.select_backends(main_window)
                yield from settle()

        unit_view = main_controller.unit_controller.view
        for role, textbox in (("source", unit_view.sources[0]), ("target", unit_view.targets[0])):
            textbox.grab_focus()
            textbox.emit("popup-menu")
            yield from settle(3)
            visit("%s text box context menu" % role)
            for menu in Gtk.Menu.get_for_attach_widget(textbox):
                menu.popdown()

        # gtkspell's items for a misspelled word, with and without
        # suggestions - if a dictionary for the target language exists.
        target = unit_view.targets[0]
        for word in ("Vertaalprogrm", "xqzvwkjhq"):
            buffer = target.get_buffer()
            buffer.set_text(word)
            buffer.place_cursor(buffer.get_start_iter())
            yield from settle()
            target.grab_focus()
            target.emit("popup-menu")
            yield from settle(3)
            visit("spelling menu for %s" % word)
            for menu in Gtk.Menu.get_for_attach_widget(target):
                menu.popdown()

        menubar = main_controller.view.gui.get_object("menubar")
        items = _leaf_menu_items(menubar)
        ids = {item: Gtk.Buildable.get_name(item) for item in items}
        items = ([i for i in items if ids[i] not in LAST_ITEMS + SKIP_ITEMS]
                 + [i for i in items if ids[i] in LAST_ITEMS])
        for item in items:
            name = ids[item] or item.get_label() or type(item).__name__
            if main_controller.store_controller.store is not None:
                main_controller.store_controller.set_modified(False)
            current_screen[0] = name
            if item.get_sensitive():
                item.activate()
            yield from settle()
            visit(name)
            yield from open_subdialogs(name)
            for window in Gtk.Window.list_toplevels():
                if window is not main_window and window.get_visible() and window.get_transient_for() is main_window:
                    window.hide()

        if main_controller.plugin_controller:
            main_controller.plugin_controller.shutdown()
        Gtk.main_quit()

    gen = driver()
    failed = []

    def step():
        # An exception reaching Virtaal's handler opens a crash dialog,
        # which waits for input no headless run can give.
        try:
            next(gen)
        except StopIteration:
            return GLib.SOURCE_REMOVE
        except Exception:
            traceback.print_exc()
            failed.append(True)
            Gtk.main_quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    GLib.timeout_add(150, step)
    app.run()
    shutil.rmtree(workdir, ignore_errors=True)
    if failed:
        sys.exit("Harvest failed; nothing written")

    with open(output, "w", encoding="utf-8") as f:
        json.dump({"strings": harvest.strings}, f, ensure_ascii=False, indent=1)
    print("Recorded %d strings to %s" % (len(harvest.strings), output))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", help="JSON file to write")
    run(parser.parse_args().output)


if __name__ == "__main__":
    main()
