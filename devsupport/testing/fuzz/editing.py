#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Fuzz the editing paths the corpus sweep doesn't reach: real key
presses, autocorrect, spelling and glossary terms with corpus text, and
every shipped interface language.

    keys        corpus target, then placeable navigation, insert placeable,
                copy source, typing with word completion, undo
    autocorrect a local correction list that expands fuzzN to each value
    spelling    corpus target with spell checking on, then its suggestions menu
    glossary    the default glossary holds corpus terms; units use them
    ui-<code>   one per language in po/LINGUAS: open, move, every mode,
                Search, Preferences, Properties, About, shortcuts
"""

import os
import time
from xml.sax.saxutils import quoteattr

from corpus import CORPUS, short

EDIT_SECTIONS = ('keys', 'autocorrect', 'spelling', 'glossary')
LINGUAS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'po', 'LINGUAS'))
SOURCE = 'Click <b>%s</b> to save {0} as file.txt on http://example.org/'


def ui_languages():
    try:
        with open(LINGUAS, encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except OSError:
        return []


def _set_option(conf, name, section, key, value):
    import configparser
    path = os.path.join(conf, name)
    parser = configparser.RawConfigParser()
    parser.read(path, encoding='utf-8')
    if not parser.has_section(section):
        parser.add_section(section)
    parser.set(section, key, value)
    with open(path, 'w', encoding='utf-8') as f:
        parser.write(f)


def _xml_safe(value):
    from translate.misc.xml_helpers import valid_chars_only
    return valid_chars_only(value)


def configure(section, conf):
    """Section-specific config, before Virtaal reads it."""
    if section == 'autocorrect':
        _set_option(conf, 'virtaal.ini', 'plugin_state', 'autocorrector', 'enabled')
        folder = os.path.join(conf, 'autocorr', 'af')
        os.makedirs(folder, exist_ok=True)
        blocks = ''.join('<block-list:block block-list:abbreviated-name="fuzz%d" block-list:name=%s/>' % (
            i, quoteattr(_xml_safe(value))) for i, (_, _, value) in enumerate(CORPUS) if _xml_safe(value))
        with open(os.path.join(folder, 'DocumentList.xml'), 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<block-list:block-list '
                    'xmlns:block-list="http://openoffice.org/2001/block-list">%s</block-list:block-list>\n' % blocks)
    elif section == 'spelling':
        _set_option(conf, 'virtaal.ini', 'plugin_state', 'spellchecker', 'enabled')
        # English has a dictionary almost everywhere.
        _set_option(conf, 'virtaal.ini', 'language', 'sourcelang', 'af')
        _set_option(conf, 'virtaal.ini', 'language', 'targetlang', 'en')
    elif section == 'glossary':
        from translate.storage import po
        store = po.pofile()
        store.updateheader(add=True, Language='af')
        for i, (_, _, value) in enumerate(CORPUS):
            if value.strip():
                store.addsourceunit(value).target = 'term%d' % i
            store.addsourceunit('file%d' % i).target = value
        store.savefile(os.path.join(conf, 'terminology.po'))


def _file(sweep, name, sources, targets=None, language='af'):
    from translate.storage import po
    store = po.pofile()
    store.updateheader(add=True, Language=language)
    store.updateheaderplural(2, '(n != 1)')
    for i, source in enumerate(sources):
        unit = store.addsourceunit(source)
        if targets:
            unit.target = targets[i]
    path = os.path.join(sweep.args.workdir, name)
    store.savefile(path)
    return path


def _press(widget, keyval, mods=0):
    from gi.repository import Gtk
    Gtk.test_widget_send_key(widget, keyval, mods)


def _target(sweep):
    return sweep.mc.unit_controller.view.targets[0]


def _replace_target(sweep, value):
    textbox = _target(sweep)
    buf = textbox.buffer
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())
    buf.delete_selection(True, True)
    textbox.grab_focus()
    buf.insert_interactive_at_cursor(value, -1, True)
    return textbox


def _clear(sweep, used, spare):
    """Leave the unit a case used empty, so a long value doesn't slow the
    next case."""
    sc = sweep.mc.store_controller
    sc.cursor.force_index(spare)
    sc.store.get_units()[used].target = ''


def run(sweep, section):
    if section.startswith('ui-'):
        yield from _ui(sweep, section)
    else:
        yield from {'keys': _keys, 'autocorrect': _autocorrect, 'spelling': _spelling,
                    'glossary': _glossary}[section](sweep)


def _keys(sweep):
    from gi.repository import Gdk
    alt, ctrl, shift = Gdk.ModifierType.MOD1_MASK, Gdk.ModifierType.CONTROL_MASK, Gdk.ModifierType.SHIFT_MASK
    sources = [SOURCE.replace('%s', 'unit %d' % i) for i in range(len(CORPUS) + 1)]
    # Translated units feed word completion with corpus words.
    yield from sweep.open_file(_file(sweep, 'keys.po', sources, [''] + [v for _, _, v in CORPUS]))
    sc = sweep.mc.store_controller
    presses = [
        (Gdk.KEY_Right, alt), (Gdk.KEY_Right, alt), (Gdk.KEY_Left, alt),  # next, next, previous placeable
        (Gdk.KEY_Down, alt),  # insert placeable
        (Gdk.KEY_Escape, 0),
        (Gdk.KEY_v, ctrl | shift),  # copy the source
        (Gdk.KEY_e, 0), (Gdk.KEY_n, 0), (Gdk.KEY_Tab, 0),  # type, accept a completion
        (Gdk.KEY_z, ctrl), (Gdk.KEY_z, ctrl | shift),  # undo, redo
        (Gdk.KEY_Home, 0), (Gdk.KEY_End, shift), (Gdk.KEY_BackSpace, 0),
    ]
    for i, (case, value) in enumerate(sweep.cases('keys'), start=1):
        try:
            sc.cursor.force_index(i % len(sources))
            yield from sweep.settle(5)
            textbox = _replace_target(sweep, value)
            yield from sweep.settle(3)
            for keyval, mods in presses:
                _press(textbox, keyval, mods)
                yield from sweep.settle(2)
        except Exception:
            sweep.failed()
        finally:
            _clear(sweep, i % len(sources), (i + 1) % len(sources))
            yield from sweep.settle(5)
    sc.set_modified(False)


def _autocorrect(sweep):
    # By corpus position, as configure() numbered them, whatever --only or a skip list leaves out.
    index = {name: i for i, (_, name, _) in enumerate(CORPUS)}
    yield from sweep.open_file(_file(sweep, 'autocorrect.po', ['Open the file %d' % i for i in range(4)]))
    sc = sweep.mc.store_controller
    for case, value in sweep.cases('autocorrect'):
        i = index[case]
        expected = _xml_safe(value)
        try:
            sc.cursor.force_index(i % 3)
            yield from sweep.settle(5)
            textbox = _replace_target(sweep, 'x fuzz%d' % i)
            textbox.buffer.insert_interactive_at_cursor(' ', -1, True)
            yield from sweep.settle(5)
            # The correction runs on idle, which a slow case can hold up.
            deadline = time.monotonic() + 30
            while expected and expected not in textbox.get_text() and time.monotonic() < deadline:
                yield
            text = textbox.get_text()
            if expected and expected not in text:
                sweep.rec.problem('autocorrect-mismatch', '', 'target is %s' % short(text))
        except Exception:
            sweep.failed()
        finally:
            _clear(sweep, i % 3, 3)
            yield from sweep.settle(5)
    sc.set_modified(False)


def _spelling(sweep):
    from gi.repository import Gtk
    # The file's language is the one checked: English, as configure() sets.
    yield from sweep.open_file(_file(sweep, 'spelling.po', ['Maak die lêer %d oop' % i for i in range(4)],
                                     language='en'))
    sc = sweep.mc.store_controller
    for i, (case, value) in enumerate(sweep.cases('spelling')):
        try:
            sc.cursor.force_index(i % 3)
            yield from sweep.settle(5)
            # Misspelt on purpose, for the suggestions menu.
            textbox = _replace_target(sweep, value + ' speling mistaek')  # codespell:ignore speling
            yield from sweep.settle(15)  # the checker runs on idle
            buf = textbox.buffer
            buf.place_cursor(buf.get_iter_at_offset(max(0, buf.get_char_count() - 3)))
            menu = Gtk.Menu()
            textbox.emit('populate-popup', menu)
            yield from sweep.settle(3)
            menu.destroy()
        except Exception:
            sweep.failed()
        finally:
            _clear(sweep, i % 3, 3)
            yield from sweep.settle(5)
    sc.set_modified(False)


def _glossary(sweep):
    from gi.repository import Gdk
    values = [v for _, _, v in CORPUS]
    sources = ['Use %s and file%d here' % (v, i) for i, v in enumerate(values)]
    yield from sweep.open_file(_file(sweep, 'glossary.po', sources))
    sc = sweep.mc.store_controller
    for i, (case, value) in enumerate(sweep.cases('glossary')):
        try:
            sc.cursor.force_index(i)
            yield from sweep.settle(15)  # terminology matching
            textbox = _target(sweep)
            textbox.grab_focus()
            _press(textbox, Gdk.KEY_Down, Gdk.ModifierType.MOD1_MASK)  # the term suggestions
            yield from sweep.settle(5)
            _press(textbox, Gdk.KEY_Escape)
            yield from sweep.settle(2)
        except Exception:
            sweep.failed()
    sc.set_modified(False)


def _ui(sweep, section):
    """Build the windows and dialogs whose text is translated."""
    from gi.repository import Gtk
    Gtk.Dialog.run = lambda dialog, *args: Gtk.ResponseType.CANCEL
    Gtk.NativeDialog.run = lambda dialog, *args: Gtk.ResponseType.CANCEL
    mc = sweep.mc
    steps = [
        ('open', lambda: None),
        ('modes', lambda: [mc.mode_controller.select_mode_by_name(name) for name in list(mc.mode_controller.modes)]
         + [mc.mode_controller.select_mode_by_name('Default')]),
        ('search', lambda: (mc.mode_controller.select_mode_by_name('Search'),
                            mc.mode_controller.modes['Search'].ent_search.set_text('file'))),
    ] + [(name, (lambda item: lambda: mc.view.gui.get_object(item).activate())(item)) for name, item in (
        ('preferences', 'mnu_prefs'), ('properties', 'mnu_properties'), ('quality checks', 'mnu_checks'),
        ('about', 'mnu_about'), ('shortcuts', 'mnu_shortcuts'))]
    from malformed import PO
    path = os.path.join(sweep.args.workdir, 'ui.po')
    with open(path, 'wb') as f:
        f.write(PO)
    for case, step in sweep.cases(section, [(None, name, call) for name, call in steps]):
        try:
            if case == 'open':
                yield from sweep.open_file(path)
                mc.store_controller.cursor.force_index(1)
            else:
                step()
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                yield
            for window in Gtk.Window.list_toplevels():
                if window is not mc.view.main_window and window.get_visible() and window.get_transient_for():
                    window.hide()
        except Exception:
            sweep.failed()
