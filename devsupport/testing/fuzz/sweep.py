#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Corpus sweep: every corpus value through one group of inputs.

Runs one section in a real Virtaal, in a fixed order, and writes each
case's problems to a results file (see record.py). fuzz_ui.py starts it
with an isolated, offline config; it isn't meant to be run on its own.

    sweep.py SECTION --workdir DIR --results FILE [--case-timeout N]
             [--only SWEEP/CASE] [--skip-file FILE]
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.abspath(os.path.join(HERE, '..', '..', '..')))

from corpus import API_ONLY, CORPUS, short  # noqa: E402

# Files with a corpus value in one field of each unit: sweep, extension, field.
SOURCE_FILES = (
    ('source', 'po', 'source'),
    ('source-xliff', 'xlf', 'source'),
    ('source-ts', 'ts', 'source'),
    ('source-tbx', 'tbx', 'source'),
    ('source-tmx', 'tmx', 'source'),
    ('context', 'po', 'context'),
    ('notes', 'po', 'notes'),
    ('plural-source', 'po', 'plural'),
)

# Section: the sweeps it runs. The parent reads this without loading GTK.
SECTIONS = {
    'target': ('target', 'target-xliff'),
    'search': ('search', 'search-regex'),
    'replace': ('replace', 'replace-all'),
    'source': tuple(sweep for sweep, _, _ in SOURCE_FILES) + ('tm-query',),
    'addterm': ('addterm-source', 'addterm-target', 'addterm-comment', 'addterm-existing'),
    'addlang': ('addlang-name', 'addlang-code', 'addlang-plural'),
    'lookup': ('lookup-name', 'lookup-url', 'lookup-query'),
    'translator': ('translator-name', 'translator-email', 'translator-team'),
}

GLib = Gtk = None

TARGET_PO = '''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"
"Language: af\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

msgid "Open the file"
msgstr ""

msgid "Save the file"
msgstr "Stoor die lêer"

msgid "%d file"
msgid_plural "%d files"
msgstr[0] "%d lêer"
msgstr[1] "%d lêers"
'''

TARGET_XLIFF = '''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
<file original="t" source-language="en" target-language="af" datatype="plaintext"><body>
<trans-unit id="1" xml:space="preserve"><source>Open the file</source></trans-unit>
<trans-unit id="2" xml:space="preserve"><source>Save the file</source><target>Stoor die lêer</target></trans-unit>
</body></file></xliff>
'''


def corpus_file(workdir, sweep, ext, field, translated=False):
    """Write a file with one unit per corpus value in the given field,
    through translate-toolkit; returns its path and the case name of each
    unit, in order. translated: the value is the translation too."""
    from translate.misc.multistring import multistring
    from translate.storage import po, tbx, tmx, ts2, xliff
    store = {
        'po': po.pofile,
        'xlf': lambda: xliff.xlifffile(sourcelanguage='en', targetlanguage='af'),
        'ts': ts2.tsfile,
        'tbx': tbx.tbxfile,
        'tmx': tmx.tmxfile,
    }[ext]()
    if ext == 'po':
        store.updateheader(add=True, Language='af')
        store.updateheaderplural(2, '(n != 1)')
    else:
        store.setsourcelanguage('en')
        store.settargetlanguage('af')
    names = []
    for _, name, value in CORPUS + API_ONLY:
        if field == 'source' and not value:
            continue  # not a unit Virtaal shows; in PO it's the header
        if ext == 'po':
            try:
                value.encode('utf-8')
            except UnicodeEncodeError:
                continue
        try:
            if field == 'source':
                unit = store.addsourceunit(value)
                if translated:
                    unit.target = value
            else:
                unit = store.addsourceunit('Open the file %d' % len(names))
                if field == 'context':
                    unit.setcontext(value)
                elif field == 'notes':
                    unit.addnote(value, 'developer')
                else:
                    unit.source = multistring(['Open %%d file %d' % len(names), value])
                    unit.target = multistring(['', ''])
        except Exception:
            continue
        names.append(name)
    path = os.path.join(workdir, '%s.%s' % (sweep, ext))
    store.savefile(path)
    return path, names


class Sweep:
    def __init__(self, args, app, recorder):
        self.args = args
        self.app = app
        self.mc = app.main_controller
        self.rec = recorder
        self.skip = set()
        if args.skip_file:
            with open(args.skip_file, encoding='utf-8') as f:
                self.skip = {tuple(item) for item in json.load(f)}

    # HELPERS #

    def settle(self, frames=3):
        for _ in range(frames):
            yield

    def cases(self, sweep, values=CORPUS):
        """(name, value) for each case to run; the case is recorded from
        its yield until the next one."""
        for _, name, value in values:
            key = (sweep, name)
            if self.args.only and self.args.only != '%s/%s' % key:
                continue
            if key in self.skip:
                continue
            self.rec.begin(sweep, name)
            yield name, value
            self.rec.end()

    def runs(self, sweep):
        """Whether any case of this sweep is to run."""
        return not self.args.only or self.args.only.startswith(sweep + '/')

    def failed(self):
        self.rec.exception(*sys.exc_info())

    def write_file(self, name, text):
        path = os.path.join(self.args.workdir, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        return path

    def open_file(self, path):
        self.mc.open_file(path)
        yield from self.settle(20)
        # Plug-ins load after the first file opens; let them finish first.
        yield from self.wait_for(lambda: self.mc.plugin_controller is not None
                                 and 'terminology' in self.mc.plugin_controller.plugins)
        yield from self.settle(20)

    def wait_for(self, condition, frames=3000):
        for _ in range(frames):
            if condition():
                return
            yield

    def fill(self, entry, value):
        """Replace an entry's text through its insert-text handling, as
        typing or pasting does."""
        entry.set_text('')
        entry.grab_focus()
        entry.insert_text(value, 0)

    def entry_text(self, entry, value, label):
        text = entry.get_text()
        if text != value:
            self.rec.note('%s holds %s' % (label, short(text)))
        return text

    def undo(self):
        self.mc.undo_controller._on_undo_activated()

    def redo(self):
        self.mc.undo_controller._on_redo_activated()

    def reload_target(self, index):
        from translate.storage import factory
        store = factory.getobject(self.mc.store_controller.store.get_filename())
        units = [u for u in store.units if not u.isheader()]
        return str(units[index].target)

    # SECTIONS #

    def target(self):
        from translate.misc.xml_helpers import valid_chars_only
        for sweep, name, text, expect in (
                ('target', 'target.po', TARGET_PO, lambda v: v),
                ('target-xliff', 'target.xlf', TARGET_XLIFF, valid_chars_only)):
            if not self.runs(sweep):
                continue
            yield from self.open_file(self.write_file(name, text))
            for case, value in self.cases(sweep):
                try:
                    yield from self._target_case(value, expect(value))
                except Exception:
                    self.failed()
                finally:
                    # Moving onto a long target is slow (#4347); don't charge
                    # that to the next case.
                    self.mc.store_controller.cursor.force_index(1)
                    self.mc.store_controller.store.get_units()[0].target = ''
                    yield from self.settle(2)
            self.mc.store_controller.set_modified(False)

    def _target_case(self, value, expected):
        sc = self.mc.store_controller
        sc.cursor.force_index(0)
        yield from self.settle(5)
        textbox = self.mc.unit_controller.view.targets[0]
        buf = textbox.buffer
        buf.select_range(buf.get_start_iter(), buf.get_end_iter())
        buf.delete_selection(True, True)
        yield from self.settle(2)
        self.mc.undo_controller.model.clear()
        textbox.grab_focus()
        buf.place_cursor(buf.get_end_iter())
        buf.insert_interactive_at_cursor(value, -1, True)
        yield from self.settle(5)
        if textbox.get_text() != expected:
            self.rec.problem('editor-mismatch', '', 'editor holds %s' % short(textbox.get_text()))
            return

        self.undo()
        yield from self.settle(5)
        if textbox.get_text() != '':
            self.rec.problem('undo-mismatch', 'undo insert', 'after undo: %s' % short(textbox.get_text()))
        self.redo()
        yield from self.settle(5)
        if textbox.get_text() != expected:
            self.rec.problem('undo-mismatch', 'redo insert', 'after redo: %s' % short(textbox.get_text()))
            return

        sc.cursor.force_index(1)
        yield from self.settle(5)
        unit = sc.store.get_units()[0]
        if str(unit.target) != expected:
            self.rec.problem('commit-mismatch', '', 'unit target %s' % short(str(unit.target)))
            return
        if not self.mc.save_file():
            self.rec.problem('save-failed', '', 'save_file() returned False')
            return
        saved = self.reload_target(0)
        if saved != expected:
            self.rec.problem('save-roundtrip', '', 'reloaded target %s' % short(saved))

    def source(self):
        sc = self.mc.store_controller
        for sweep, ext, field in SOURCE_FILES:
            if not self.runs(sweep):
                continue
            path, names = corpus_file(self.args.workdir, sweep, ext, field)
            yield from self.open_file(path)
            units = sc.store.get_units()
            if len(units) != len(names):
                self.rec.problem('setup', 'unit count', '%s: %d units for %d values' % (sweep, len(units), len(names)))
                continue
            for case, index in self.cases(sweep, [(None, name, i) for i, name in enumerate(names)]):
                try:
                    sc.cursor.force_index(index)
                    # Time for the TM query, terminology and quality checks.
                    yield from self.settle(25)
                    strings = getattr(units[index].source, 'strings', [str(units[index].source)])
                    for textbox, expected in zip(self.mc.unit_controller.view.sources, strings):
                        if textbox.get_text() != str(expected):
                            self.rec.problem('display-mismatch', '', 'source shows %s' % short(textbox.get_text()))
                except Exception:
                    self.failed()
            sc.set_modified(False)

        if not self.runs('tm-query'):
            return
        from translate.storage import factory

        from virtaal.common import pan_app
        from virtaal.support.tmdb import TMDB
        db = TMDB(os.path.join(pan_app.get_config_dir(), 'tm.db'))
        # Queries only reach the full-text search once the TM has entries.
        path, _ = corpus_file(self.args.workdir, 'tm-seed', 'po', 'source', translated=True)
        db.add_store(factory.getobject(path), 'en', 'af')
        for case, value in self.cases('tm-query', CORPUS + API_ONLY):
            try:
                db.translate_unit(value, 'en', 'af')
            except Exception:
                self.failed()

    def search(self):
        path, _ = corpus_file(self.args.workdir, 'search', 'po', 'source', translated=True)
        yield from self.open_file(path)
        self.mc.mode_controller.select_mode_by_name('Search')
        yield from self.settle(10)
        mode = self.mc.mode_controller.modes['Search']
        for sweep, regex in (('search', False), ('search-regex', True)):
            for case, value in self.cases(sweep):
                try:
                    mode.chk_regex.set_active(regex)
                    mode.ent_search.set_text('')
                    yield from self.settle(1)
                    self.fill(mode.ent_search, value)
                    yield from self.settle(3)
                    self.entry_text(mode.ent_search, value, 'search entry')
                    mode._on_entry_activate(mode.ent_search)
                    yield from self.settle(3)
                    for _ in range(3):
                        mode._on_search_next()
                        yield from self.settle(2)
                except Exception:
                    self.failed()
        mode.chk_regex.set_active(False)

    def replace(self):
        yield from self.open_file(self.write_file('replace.po', TARGET_PO))
        self.mc.mode_controller.select_mode_by_name('Search')
        yield from self.settle(10)
        mode = self.mc.mode_controller.modes['Search']
        for sweep, replace_all in (('replace', False), ('replace-all', True)):
            for case, value in self.cases(sweep):
                try:
                    yield from self._replace_case(mode, value, replace_all)
                except Exception:
                    self.failed()
        self.mc.store_controller.set_modified(False)

    def _replace_case(self, mode, value, replace_all):
        sc = self.mc.store_controller
        sc.cursor.force_index(0)
        yield from self.settle(3)
        self.mc.unit_controller.set_unit_target(0, 'leer')
        yield from self.settle(3)
        self.mc.undo_controller.model.clear()
        mode.chk_regex.set_active(False)
        mode.ent_search.set_text('leer')
        self.fill(mode.ent_replace, value)
        yield from self.settle(3)
        replacement = self.entry_text(mode.ent_replace, value, 'replace entry')
        mode.chk_replace_all.set_active(replace_all)
        mode._on_replace_clicked(None)
        yield from self.settle(5)
        now = str(sc.store.get_units()[0].target)
        if now != replacement:
            self.rec.problem('replace-mismatch', '', 'target now %s' % short(now))
            return
        self.undo()
        yield from self.settle(5)
        now = str(sc.store.get_units()[0].target)
        if now != 'leer':
            self.rec.problem('undo-mismatch', 'undo replace', 'after undo: %s' % short(now))

    def addterm(self):
        from translate.storage import factory
        yield from self.open_file(self.write_file('addterm.po', TARGET_PO))
        terminology = self.mc.plugin_controller.plugins['terminology'].controller
        localfile = terminology.plugin_controller.plugins['localfile']
        dialog = localfile.view.addterm
        dialog.reset()
        glossary = localfile.config['extendfile']

        for field in ('source', 'target', 'comment'):
            for i, (case, value) in enumerate(self.cases('addterm-' + field)):
                try:
                    dialog.reset()
                    dialog.cmb_termfile.set_active(0)
                    self.fill(dialog.ent_source, value if field == 'source' else '%s-bron%d' % (field, i))
                    self.fill(dialog.ent_target, value if field == 'target' else '%s-doel%d' % (field, i))
                    yield from self.settle(2)
                    source = dialog.ent_source.get_text()
                    target = dialog.ent_target.get_text()
                    dialog.txt_comment.get_buffer().set_text(value if field == 'comment' else '')
                    dialog._on_entry_changed(None)
                    yield from self.settle(2)
                    if not dialog.btn_add_term.props.sensitive:
                        continue
                    if not (source.strip() and target.strip()):
                        self.rec.problem('accepted-blank', 'blank term',
                                         'OK enabled for (%s, %s)' % (short(source), short(target)))
                    dialog.add_term_unit(source, target)
                    yield from self.settle(5)
                    unit = factory.getobject(glossary).units[-1]
                    if not str(unit.source):
                        self.rec.problem('file-invalid', 'second header', 'the new term has an empty source')
                    if (str(unit.source), str(unit.target)) != (source, target):
                        self.rec.problem('term-roundtrip', '', 'saved (%s, %s)' % (short(str(unit.source)),
                                                                                 short(str(unit.target))))
                    elif field == 'comment' and value.strip() and value not in unit.getnotes():
                        self.rec.problem('term-roundtrip', 'comment', 'comment saved as %s' % short(unit.getnotes()))
                except Exception:
                    self.failed()

        # Existing translations are listed when the source is typed again.
        store = localfile.stores[0]
        for i, (case, value) in enumerate(self.cases('addterm-existing')):
            try:
                unit = store.addsourceunit('existing%d' % i)
                unit.target = value
                dialog.reset()
                self.fill(dialog.ent_source, 'existing%d' % i)
                self.fill(dialog.ent_target, 'another translation')
                yield from self.settle(2)
                dialog._on_entry_changed(None)
                yield from self.settle(2)
                shown = dialog.lbl_add_term_errors.get_text()
                # The label shows CR and CRLF as LF.
                if shown != 'Existing translations: ' + value.replace('\r\n', '\n').replace('\r', '\n'):
                    self.rec.problem('display-mismatch', 'existing translations', 'label shows %s' % short(shown))
            except Exception:
                self.failed()

    def addlang(self):
        from translate.storage import factory

        from virtaal.common import pan_app
        from virtaal.models.langmodel import LanguageModel
        from virtaal.views.widgets.langadddialog import LanguageAddDialog
        no_plural = TARGET_PO.replace('"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n', '')
        yield from self.open_file(self.write_file('addlang.po', no_plural))
        lc = self.mc.lang_controller
        dialog = LanguageAddDialog()
        langs_ini = os.path.join(pan_app.get_config_dir(), 'langs.ini')
        original_langs = dict(LanguageModel.languages)
        original_pair = (lc.source_lang, lc.target_lang)

        for field in ('name', 'code', 'plural'):
            for i, (case, value) in enumerate(self.cases('addlang-' + field)):
                try:
                    if field == 'plural':
                        # The equation is only written into a file that has none.
                        yield from self.open_file(self.write_file('addlang-%d.po' % i, no_plural))
                    dialog.clear()
                    self.fill(dialog.ent_langname, value if field == 'name' else 'Fuzzish %d' % i)
                    self.fill(dialog.ent_langcode, value if field == 'code' else 'fz%d' % i)
                    self.fill(dialog.ent_plural, value if field == 'plural' else '(n != 1)')
                    yield from self.settle(3)
                    name, code, plural = dialog.langname, dialog.langcode, dialog.plural
                    if dialog.check_input_sanity():
                        continue
                    # What LanguageView._on_addlang_clicked does.
                    LanguageModel.languages[code] = (name, dialog.nplurals, plural)
                    lc.new_langs.append(code)
                    # As choosing the pair in the language dialog does.
                    lc.set_language_pair(lc.source_lang, code)
                    yield from self.settle(5)
                    self.mc.store_controller.set_modified(True)
                    if self.mc.save_file():
                        saved = factory.getobject(self.mc.store_controller.store.get_filename())
                        self._check_plural_header(saved)
                    # Quit-time persistence, then what the next start-up reads.
                    lc._on_quit(self.mc)
                    pan_app.settings.write()
                    reread = pan_app.load_config(langs_ini)
                    if reread.get(code, {}).get('name') != name or reread.get(code, {}).get('plural') != plural:
                        self.rec.problem('config-roundtrip', 'langs.ini',
                                         'read back %s' % short(str(reread.get(code))))
                    settings = pan_app.Settings(pan_app.settings.filename)
                    previous, pan_app.settings = pan_app.settings, settings
                    try:
                        lc._load_recent()
                    finally:
                        pan_app.settings = previous
                except Exception:
                    self.failed()
                finally:
                    lc.source_lang, lc.target_lang = original_pair
                    LanguageModel.languages.clear()
                    LanguageModel.languages.update(original_langs)
                    lc.new_langs[:] = []
                    lc.recent_pairs = [p for p in lc.recent_pairs
                                       if p[0].code in original_langs and p[1].code in original_langs]
                    lc.save_recent()
                    if os.path.exists(langs_ini):
                        os.remove(langs_ini)

    def _check_plural_header(self, store):
        import gettext
        try:
            nplurals, plural = store.getheaderplural()
            if plural:
                gettext.c2py(plural)
        except Exception as error:
            self.rec.problem('file-invalid', 'Plural-Forms', 'saved Plural-Forms: %r' % (error,))

    def lookup(self):
        from virtaal.plugins.lookup.models.weblookup import WebLookupAddDialog, _slugify
        yield from self.open_file(self.write_file('lookup.po', TARGET_PO))
        lookup = self.mc.plugin_controller.plugins['lookup'].controller
        model = lookup.plugin_controller.plugins['weblookup']
        builtins = list(model.URLDATA)
        dialog = WebLookupAddDialog(self.mc.view.main_window)

        for field in ('name', 'url', 'query'):
            for i, (case, value) in enumerate(self.cases('lookup-' + field)):
                try:
                    if field == 'query':
                        # The right-click "Look up" menu for selected text.
                        model.create_menu_items(value, 'source', 'en', 'af', None)
                        continue
                    dialog.taken_ids = {u['id'] for u in builtins}
                    self.fill(dialog.ent_url_name, value if field == 'name' else 'Fuzz site %d' % i)
                    self.fill(dialog.ent_url, value if field == 'url' else 'https://example.org/?q=%(query)s')
                    yield from self.settle(3)
                    name, url = dialog.ent_url_name.get_text(), dialog.ent_url.get_text()
                    dialog._update_ok_sensitivity()
                    if not dialog.btn_url_ok.get_sensitive():
                        continue
                    entry = {'id': _slugify(name), 'display_name': name, 'url': url, 'quoted': False, 'enabled': True}
                    model.URLDATA = builtins + [entry]
                    model._save_urldata()
                    model._load_urldata()
                    custom = [u for u in model.URLDATA if u.get('id') == entry['id']]
                    if not custom or (custom[0]['display_name'], custom[0]['url']) != (name, url):
                        self.rec.problem('config-roundtrip', 'weblookup.ini',
                                         'read back %s' % short(str(custom[0] if custom else None)))
                    model.create_menu_items('word', 'source', 'en', 'af', None)
                except Exception:
                    self.failed()
                finally:
                    model.URLDATA = list(builtins)
                    model._save_urldata()

    def translator(self):
        from translate.storage import factory

        from virtaal.common import pan_app
        yield from self.open_file(self.write_file('translator.po', TARGET_PO))
        window = Gtk.Window()
        entry = Gtk.Entry()
        window.add(entry)
        window.show_all()
        expected_fields = {'Project-Id-Version', 'Report-Msgid-Bugs-To', 'POT-Creation-Date', 'PO-Revision-Date',
                           'Last-Translator', 'Language-Team', 'Language', 'MIME-Version', 'Content-Type',
                           'Content-Transfer-Encoding', 'Plural-Forms', 'X-Generator'}
        for field in ('name', 'email', 'team'):
            for i, (case, value) in enumerate(self.cases('translator-' + field)):
                try:
                    # A header changed by an earlier case would be blamed on this one.
                    yield from self.open_file(self.write_file('translator-%s-%d.po' % (field, i), TARGET_PO))
                    self.fill(entry, value)
                    yield from self.settle(2)
                    details = {'name': 'Fuzz Tester', 'email': 'fuzz@example.org', 'team': 'Team'}
                    details[field] = entry.get_text()
                    for key, text in details.items():
                        pan_app.settings.translator[key] = text
                    pan_app.settings.write()
                    if pan_app.Settings(pan_app.settings.filename).translator[field] != details[field]:
                        self.rec.problem('config-roundtrip', 'virtaal.ini', 'translator %s read back differently' % field)
                    self.mc.store_controller.set_modified(True)
                    if self.mc.save_file():
                        header = factory.getobject(self.mc.store_controller.store.get_filename()).parseheader()
                        extra = set(header) - expected_fields
                        if extra or header.get('Plural-Forms') != 'nplurals=2; plural=(n != 1);':
                            self.rec.problem('header-injection', '', 'header fields %r, Plural-Forms %r' % (
                                sorted(extra), header.get('Plural-Forms')))
                except Exception:
                    self.failed()
        for key, text in (('name', 'Fuzz Tester'), ('email', 'fuzz@example.org'), ('team', '')):
            pan_app.settings.translator[key] = text


def main():
    global GLib, Gtk
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import GLib, Gtk
    from record import Recorder

    parser = argparse.ArgumentParser()
    parser.add_argument('section', choices=SECTIONS)
    parser.add_argument('--workdir', required=True)
    parser.add_argument('--results', required=True)
    parser.add_argument('--case-timeout', type=int, default=60)
    parser.add_argument('--only')
    parser.add_argument('--skip-file')
    args = parser.parse_args()

    recorder = Recorder(args.results, args.case_timeout)
    recorder.sweep = args.section
    recorder.install()

    from virtaal.common import pan_app
    pan_app.settings.translator['name'] = 'Fuzz Tester'
    pan_app.settings.translator['email'] = 'fuzz@example.org'
    from virtaal.main import Virtaal

    app = Virtaal('')
    # Virtaal installs its crash dialog as the excepthook.
    sys.excepthook = recorder.exception
    recorder.stub_dialogs(app.main_controller)
    app.main_controller.view.main_window.resize(1000, 700)
    sweep = Sweep(args, app, recorder)

    def driver():
        yield from sweep.settle(20)
        yield from getattr(sweep, args.section)()
        recorder.done()
        if app.main_controller.plugin_controller:
            app.main_controller.plugin_controller.shutdown()
        os._exit(0)

    steps = driver()
    GLib.timeout_add(20, lambda: next(steps, False) is not False)
    app.run()


if __name__ == '__main__':
    main()
