#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""How long a long paste into a spell-checked text box takes (#4443),
through the spell checker plugin and through GtkSpell alone - for the
packaged builds' CI:
    virtaal --run-module virtaal.support.spelling_timing LANG [OUTPUT]"""

import sys
import time

FILLER = 'Lorem ipsum dolor sit amet. '
SIZES = (2000, 10000, 100000)


def _pump(seconds=300):
    """Runs the main loop until nothing is pending; returns how long that took."""
    from gi.repository import GLib
    context = GLib.MainContext.default()
    start = time.perf_counter()
    while context.pending() and time.perf_counter() - start < seconds:
        context.iteration(False)
    return time.perf_counter() - start


def _paste(view, text):
    """Inserts text as a paste does, timing the insert and what it left
        for the main loop."""
    buffer = view.get_buffer()
    buffer.set_text('')
    _pump()
    start = time.perf_counter()
    buffer.begin_user_action()
    buffer.insert_interactive_at_cursor(text, -1, True)
    buffer.end_user_action()
    inserted = time.perf_counter() - start
    return inserted, inserted + _pump()


def _type(view, text):
    """The longest single keystroke, typing text."""
    buffer = view.get_buffer()
    buffer.set_text('')
    _pump()
    longest = 0
    for char in text:
        start = time.perf_counter()
        buffer.begin_user_action()
        buffer.insert_interactive_at_cursor(char, -1, True)
        buffer.end_user_action()
        _pump()
        longest = max(longest, time.perf_counter() - start)
    return longest


def _marked(view):
    from virtaal.support.enchant_compat import marked_words
    return len(marked_words(view.get_buffer()))


def _plugin_view(lang):
    """A text view the spell checker plugin checks in lang."""
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import GObject, Gtk

    from virtaal.plugins.spellchecker import Plugin

    signal = (GObject.SignalFlags.RUN_FIRST, None, (object, object))

    class UnitView(GObject.Object):
        __gsignals__ = {'textview-language-changed': signal, 'sources-created': signal,
                        'targets-created': signal}

    class LangController(GObject.Object):
        __gsignals__ = {'dictionary-installed': (GObject.SignalFlags.RUN_FIRST, None, (object,))}

    view = Gtk.TextView()
    unit_view = UnitView()
    unit_view.sources, unit_view.targets = [], [view]
    lang_controller = LangController()
    lang_controller.source_lang = lang_controller.target_lang = type('Lang', (), {'code': lang})
    controller = type('MainController', (), {})()
    controller.unit_controller = type('UnitController', (), {'view': unit_view})
    controller.lang_controller = lang_controller
    plugin = Plugin('spellchecker', controller)
    _pump()
    return plugin, view


def _gtkspell_view(lang):
    import gi
    gi.require_version('GtkSpell', '3.0')
    from gi.repository import Gtk, GtkSpell
    view = Gtk.TextView()
    checker = GtkSpell.Checker()
    checker.set_language(lang)
    checker.attach(view)
    return checker, view


def timings(lang, sizes=SIZES):
    """Report lines: per size, the insert's time and the time until the
        main loop is idle, through the plugin and through GtkSpell alone;
        and the longest keystroke typing a sentence with the plugin."""
    import gi
    gi.require_version('Gtk', '3.0')
    lines = []
    plugin, view = _plugin_view(lang)
    lines.append('plugin: %s' % ('checking' if getattr(view, 'spell_lang', None) else 'not checking'))
    lines.append('typing: longest keystroke %.3f s, %d marked' % (_type(view, 'This is a tset of typing'), _marked(view)))
    for size in sizes:
        text = (FILLER * (size // len(FILLER) + 1))[:size]
        inserted, idle = _paste(view, text)
        lines.append('plugin %d: insert %.3f s, idle %.3f s, %d marked' % (size, inserted, idle, _marked(view)))
    plugin.destroy()
    # GtkSpell alone takes minutes for 100k characters.
    checker, view = _gtkspell_view(lang)
    for size in [s for s in sizes if s <= 10000]:
        text = (FILLER * (size // len(FILLER) + 1))[:size]
        inserted, idle = _paste(view, text)
        lines.append('gtkspell %d: insert %.3f s, idle %.3f s, %d marked' % (size, inserted, idle, _marked(view)))
    checker.detach()
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    # The plugin's labels, outside the app.
    import builtins
    builtins.__dict__.setdefault('_', str)
    result = timings(sys.argv[1] if len(sys.argv) > 1 else 'en_US')
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'w', encoding='utf-8') as f:
            f.write(result)
    else:
        sys.stdout.write(result)
