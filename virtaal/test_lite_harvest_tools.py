#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os

import pytest

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "devsupport", "pseudo-translation")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(TOOLS_DIR, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def resolve():
    return _load("resolve_sources")


@pytest.fixture(scope="module")
def templates():
    return _load("write_lite_templates")


def _catalogs(resolve, domain, originals):
    entries = []
    for original in originals:
        for form in original.rpartition("\x04")[2].split("\0"):
            entries.append((original, form, resolve.msgid_pattern(form)))
    return {domain: entries}


@pytest.mark.parametrize("form, shown, matches", [
    ("Open '%s'", "Open 'af.po'", True),
    ("%.1f KB", "1.5 KB", True),
    ("100%% done", "100% done", True),
    # Ends at a word boundary, so composite strings resolve.
    ("_Save", "_Saved", False),
    ("_Save", "_Save", True),
])
def test_msgid_pattern(resolve, form, shown, matches):
    assert bool(resolve.msgid_pattern(form).match(shown)) == matches


def test_resolve_text_takes_the_longest_match(resolve):
    catalogs = _catalogs(resolve, "gtk30", ["_Save", "Save _As"])

    assert resolve.resolve_text("gtk:Save _As", catalogs) == [("gtk30", "Save _As")]


def test_resolve_text_reads_a_lite_gap_marker_as_its_tag(resolve):
    catalogs = _catalogs(resolve, "gtk30", ["_Help"])

    assert resolve.resolve_text("gtk!:_Help", catalogs) == [("gtk30", "_Help")]


def test_resolve_text_prefers_literal_text_over_placeholders(resolve):
    catalogs = _catalogs(resolve, "glib20", ["format-size\x04%.1f", "kB"])

    assert resolve.resolve_text("glib:kB", catalogs) == [("glib20", "kB")]


def test_resolve_text_keeps_every_context_with_the_same_text(resolve):
    catalogs = _catalogs(resolve, "gtk30", ["_Save", "Stock label\x04_Save"])

    assert sorted(resolve.resolve_text("gtk:_Save", catalogs)) == [
        ("gtk30", "Stock label\x04_Save"), ("gtk30", "_Save")]


def test_resolve_text_resolves_each_tag_in_a_composite_string(resolve):
    catalogs = {**_catalogs(resolve, "iso639-3", ["English", "Afrikaans"]),
                **_catalogs(resolve, "gtk30", ["%s / %s available"])}

    assert resolve.resolve_text("vt:_1. iso:English → iso:Afrikaans", catalogs) == [
        ("iso639-3", "English"), ("iso639-3", "Afrikaans")]


def test_load_catalogs_matches_msgids_without_their_markup(resolve, tmp_path):
    # The harvest records labels' text, not their Pango markup.
    generator = _load("generate_pseudo_translation")
    mo_dir = tmp_path / "pseudo-source" / "LC_MESSAGES"
    mo_dir.mkdir(parents=True)
    generator.write_mo(str(mo_dir / "gtkspell3.mo"), {"<i>(no suggestions)</i>": "spell:<i>(no suggestions)</i>"})

    catalogs = resolve.load_catalogs(str(tmp_path))

    assert resolve.resolve_text("spell:(no suggestions)", catalogs) == [("gtkspell3", "<i>(no suggestions)</i>")]


def test_resolve_text_reports_a_tag_nothing_matches(resolve):
    assert resolve.resolve_text("gtk:Unknown", _catalogs(resolve, "gtk30", ["_Save"])) == [("gtk30", None)]


@pytest.mark.parametrize("within, window, expected", [
    ("Menu", "Window 'vt:Virtaal'", "menus"),
    ("", "Dialog 'vt:Add Term'", "Add Term dialog"),
    ("", "Dialog 'gtk!:About'", "About dialog"),
    ("", "MessageDialog ''", "message dialogs"),
    ("", "Window 'vt:quality-checks.po - Virtaal'", "main window"),
    ("", "Window None", "main window"),
    ("", "FileChooserDialog None", None),
])
def test_place(templates, within, window, expected):
    assert templates._place(within, window) == expected


def test_harvested_leaves_out_file_chooser_only_strings(templates, tmp_path):
    resolved = tmp_path / "resolved.json"
    resolved.write_text(
        '{"gtk30": ['
        '{"original": "Computer", "screens": [], "within": ["FileChooser"], "windows": ["FileChooserDialog None"]},'
        '{"original": "_Open", "screens": [], "within": ["", "FileChooser"], "windows": ["Window None"]}'
        '], "glib20": []}', encoding="utf-8")

    found = templates.harvested([str(resolved)])

    assert set(found["gtk30"]) == {"_Open"}


def test_merge_keeps_each_translation_language(templates, tmp_path, monkeypatch):
    monkeypatch.setattr(templates, "LITE_DIR", str(tmp_path))
    domain = tmp_path / "glib20"
    domain.mkdir()
    header = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n"Language: %s\\n"\n\n'
    (domain / "glib20.pot").write_text(header % "templates" + 'msgid "kB"\nmsgstr ""\n', encoding="utf-8")
    (domain / "af.po").write_text(header % "af" + 'msgid "kB"\nmsgstr "kG"\n', encoding="utf-8")

    templates.merge("glib20", templates.write_template("glib20", {"kB": set()}))

    assert '"Language: af\\n"' in (domain / "af.po").read_text(encoding="utf-8")


def test_write_template_replaces_where_a_message_was_seen(templates, tmp_path, monkeypatch):
    monkeypatch.setattr(templates, "LITE_DIR", str(tmp_path))
    (tmp_path / "gtk30").mkdir()
    (tmp_path / "gtk30" / "gtk30.pot").write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        '#. Help->About\nmsgid "_About"\nmsgstr ""\n', encoding="utf-8")

    for _ in range(2):
        path = templates.write_template("gtk30", {"_About": {"menus"}})

    text = open(path, encoding="utf-8").read()
    assert "#. Help->About\n#. Seen in: menus\nmsgid" in text


def test_write_template_starts_a_new_domain(templates, tmp_path, monkeypatch):
    monkeypatch.setattr(templates, "LITE_DIR", str(tmp_path))

    path = templates.write_template("gtk-mac-integration", {"Quit %s": set()})

    text = open(path, encoding="utf-8").read()
    assert '"Project-Id-Version: gtk-mac-integration lite\\n"' in text
    assert 'msgid "Quit %s"' in text


@pytest.fixture
def lite_catalogs(tmp_path, monkeypatch):
    module = _load("update_lite_catalogs")
    monkeypatch.setattr(module, "LITE_DIR", str(tmp_path))
    monkeypatch.setattr(module, "LINGUAS", str(tmp_path / "LINGUAS-lite"))
    (tmp_path / "mac").mkdir()
    (tmp_path / "mac" / "mac.pot").write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "Quit %s"\nmsgstr ""\n\nmsgid "Show All"\nmsgstr ""\n', encoding="utf-8")
    return module, tmp_path / "mac"


def test_lite_catalog_is_retired_when_upstream_translates_everything(lite_catalogs):
    module, domain_dir = lite_catalogs
    (domain_dir / "fr.po").write_text('msgid "Show All"\nmsgstr "Tout"\n', encoding="utf-8")

    translated = module.update("mac", "fr", {("", "Quit %s"): "Quitter %s", ("", "Show All"): "Tout afficher"})

    assert translated == 0
    assert not (domain_dir / "fr.po").exists()


def test_lite_catalog_keeps_its_translations_and_fills_in_upstreams(lite_catalogs):
    from translate.storage import factory

    module, domain_dir = lite_catalogs
    (domain_dir / "af.po").write_text(
        'msgid ""\nmsgstr ""\n"Language: af\\n"\n\nmsgid "Show All"\nmsgstr "Wys alles"\n', encoding="utf-8")

    translated = module.update("mac", "af", {("", "Quit %s"): "Verlaat %s"})

    targets = {str(u.source): str(u.target) for u in factory.getobject(str(domain_dir / "af.po")).units
               if not u.isheader()}
    assert translated == 2
    assert targets == {"Quit %s": "Verlaat %s", "Show All": "Wys alles"}


def test_lite_catalog_keeps_fuzzy_work_and_translator_comments(lite_catalogs):
    from translate.storage import factory

    module, domain_dir = lite_catalogs
    (domain_dir / "am.po").write_text(
        'msgid ""\nmsgstr ""\n"Language: am\\n"\n\n'
        '# (review) capitals\nmsgid "Show All"\nmsgstr "Wys alles"\n\n'
        '#, fuzzy\nmsgid "Quit %s"\nmsgstr "Verlaat %s"\n', encoding="utf-8")

    translated = module.update("mac", "am", {})

    units = {str(u.source): u for u in factory.getobject(str(domain_dir / "am.po")).units if not u.isheader()}
    assert translated == 1
    assert units["Show All"].getnotes("translator") == "(review) capitals"
    assert units["Quit %s"].isfuzzy() and str(units["Quit %s"].target) == "Verlaat %s"


def test_lite_catalog_takes_upstream_over_its_fuzzy_work(lite_catalogs):
    from translate.storage import factory

    module, domain_dir = lite_catalogs
    (domain_dir / "am.po").write_text('#, fuzzy\nmsgid "Quit %s"\nmsgstr "Verlaat %s"\n', encoding="utf-8")

    module.update("mac", "am", {("", "Quit %s"): "Verlaat tog %s"})

    units = {str(u.source): u for u in factory.getobject(str(domain_dir / "am.po")).units if not u.isheader()}
    assert not units["Quit %s"].isfuzzy() and str(units["Quit %s"].target) == "Verlaat tog %s"


def test_linguas_lists_only_lite_catalogs_that_translate_something(lite_catalogs):
    module, domain_dir = lite_catalogs
    linguas = domain_dir.parent / "LINGUAS-lite"
    linguas.write_text("gtk30/zu\nmac/old\n", encoding="utf-8")

    module.write_linguas({"mac": ["af"]})

    assert linguas.read_text(encoding="utf-8") == "gtk30/zu\nmac/af\n"
