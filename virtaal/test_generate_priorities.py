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

PRIORITIES = {
    name: {"name": "Level %s" % name, "order": order, "description": "Level %s messages." % name}
    for order, name in enumerate(("1", "1~", "2", "3", "x"), 1)
}

RULES = {
    "priorities": PRIORITIES,
    "seen": [
        {"priority": "3", "within": "^FileChooser$"},
        {"priority": "1", "screen": "^welcome screen$", "window": "^Window ('Virtaal'|None)$"},
        {"priority": "2", "window": "'Settings'"},
        {"priority": "1~", "window": "^Window 'Virtaal'"},
        {"priority": "3"},
    ],
    "unseen": [{"priority": "2", "file": "^virtaal/support/tutorial\\.py"}],
    "override": [{"priority": "1~", "msgids": ["Choose a Translation File"]}],
    "x": {"msgids": ["GNOME"], "patterns": ["^https?://"]},
}


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("generate_priorities",
                                                  os.path.join(TOOLS_DIR, "generate_priorities.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _catalogs(gen, domain, originals):
    resolve = gen._resolver()
    return {domain: [(original, form, resolve.msgid_pattern(form))
                     for original in originals for form in original.rpartition("\x04")[2].split("\0")]}


def _record(text, screen="welcome screen", window="Window 'vt:Virtaal'", within="", shown=True):
    return {"text": text, "screen": screen, "window": window, "within": within, "shown": shown}


@pytest.mark.parametrize("screen, window, within, expected", [
    ("welcome screen", "Window 'vt:Virtaal'", "Menu", "1"),
    ("file open", "Window 'vt:Virtaal'", "", "1~"),
    ("mnu_prefs > vt:Settings", "Dialog 'vt:Settings'", "", "2"),
    ("welcome screen", "FileChooserDialog None", "FileChooser", "3"),
    ("mnu_about", "AboutDialog None", "", "3"),
])
def test_sighting_takes_the_first_matching_rule(gen, screen, window, within, expected):
    assert gen.sighting_level(RULES, screen, window, within) == expected


def test_a_message_takes_its_lowest_level_and_ignores_hidden_sightings(gen):
    harvest = {"strings": [
        _record("vt:_Find…", screen="file open"),
        _record("vt:_Find…"),
        _record("vt:Settings", shown=False),
    ]}
    catalogs = _catalogs(gen, "virtaal", ["_Find…", "Settings"])

    assert gen.seen_levels([harvest], catalogs, RULES) == {"virtaal": {"_Find…": "1"}}


def test_tooltips_count_at_most_as_their_priority(gen):
    rules = dict(RULES, tooltips={"priority": "2"})
    harvest = {"strings": [
        dict(_record("vt:Move one step forward"), tooltip=True),
        dict(_record("vt:Add Term", window="Dialog 'vt:Add Term'"), tooltip=True),
        dict(_record("vt:_Find…"), tooltip=True),
        _record("vt:_Find…"),
    ]}
    catalogs = _catalogs(gen, "virtaal", ["Move one step forward", "Add Term", "_Find…"])

    assert gen.seen_levels([harvest], catalogs, rules) == {
        "virtaal": {"Move one step forward": "2", "Add Term": "3", "_Find…": "1"}}


def test_a_plural_is_keyed_by_its_singular(gen):
    harvest = {"strings": [_record("vt:1 unit", screen="file open")]}
    catalogs = _catalogs(gen, "virtaal", ["%d unit\0%d units"])

    assert gen.seen_levels([harvest], catalogs, RULES) == {"virtaal": {"%d unit": "1~"}}


def test_unseen_messages_take_their_files_level(gen):
    messages = {
        "Brackets": ["virtaal/controllers/checkscontroller.py"],
        "Welcome to the tutorial": ["virtaal/support/tutorial.py"],
        "usage: ": ["virtaal/cli.py"],
    }
    levels = gen.assign({"virtaal": {"Brackets": "1~"}}, messages, RULES)["virtaal"]

    assert levels == {"Brackets": "1~", "Welcome to the tutorial": "2", "usage: ": "3"}


def test_overrides_replace_the_level_and_x_replaces_everything(gen):
    messages = {"Choose a Translation File": ["virtaal/views/mainview.py"],
                "GNOME": ["virtaal/controllers/checkscontroller.py"],
                "https://example.org": ["virtaal/views/mainview.py"]}
    levels = gen.assign({"virtaal": {"GNOME": "1~"}}, messages, RULES)["virtaal"]

    assert levels == {"Choose a Translation File": "1~", "GNOME": "x", "https://example.org": "x"}


def test_language_and_country_names_come_from_the_rules_not_the_harvest(gen):
    # The harvest's own language pair (English to Afrikaans) is no guide.
    rules = {"priorities": PRIORITIES, "names": {"english": "1", "supported": "2", "wider": {"priority": "2", "languages": ["fr", "sw"]}}}
    levels = {"iso639-3": {"Afrikaans": "1~", "English": "1~"}, "iso3166-1": {"Lesotho": "2"}, "virtaal": {"_Find…": "1"}}

    # Named as Virtaal looks them up: by the catalog's own name for the
    # code first ("Swahili (macrolanguage)"), then translate-toolkit's;
    # "Portuguese (Brazil)" is two messages, "Catalan; Valencian
    # (Valencia)" just Catalan, and Songhai has no catalog entry.
    assert gen.apply_names(levels, rules, ["zu", "pt_BR", "zh_TW", "ca@valencia", "son"]) == {
        "virtaal": {"_Find…": "1"},
        "iso639-3": {"Zulu": "2", "Portuguese": "2", "Chinese": "2", "Catalan": "2", "French": "2",
                     "Swahili (macrolanguage)": "2", "English": "1"},
        "iso3166-1": {"Brazil": "2", "Taiwan": "2"},
    }


def test_a_message_takes_the_priority_ordered_first(gen):
    # Names don't rank: order does.
    harvest = {"strings": [
        {"screen": "file open", "window": "Window 'Settings'", "within": None, "text": "vt:Brackets"},
        {"screen": "file open", "window": "Window 'Virtaal'", "within": None, "text": "vt:Brackets"},
    ]}
    catalogs = _catalogs(gen, "virtaal", ["Brackets"])
    reordered = dict(RULES, priorities=dict(PRIORITIES, **{"2": dict(PRIORITIES["2"], order=0)}))

    assert gen.seen_levels([harvest], catalogs, RULES) == {"virtaal": {"Brackets": "1~"}}
    assert gen.seen_levels([harvest], catalogs, reordered) == {"virtaal": {"Brackets": "2"}}


@pytest.mark.parametrize("change, error", [
    ({"override": [{"priority": "4", "msgids": ["Open"]}]}, "Priority '4' isn't defined"),
    ({"priorities": dict(PRIORITIES, **{"3": dict(PRIORITIES["3"], order=1)})}, "same order"),
])
def test_rules_must_use_defined_priorities_in_a_clear_order(gen, change, error):
    with pytest.raises(ValueError, match=error):
        gen.check_rules(dict(RULES, **change))


def test_the_file_lists_the_priorities_in_order(gen):
    rules = dict(RULES, priorities=dict(PRIORITIES, **{"x": dict(PRIORITIES["x"], order=0)}))

    data = gen.to_file({"virtaal": {"GNOME": "x", "_Find…": "1"}}, "2026-10-09", rules)

    assert [p["id"] for p in data["priorities"]] == ["x", "1", "1~", "2", "3"]
    assert data["priorities"][1] == {"id": "1", "name": "Level 1", "order": 1, "description": "Level 1 messages."}
    assert list(data["domains"]["virtaal"]) == ["x", "1"]


def test_report_warns_when_the_definitions_change(gen):
    text, annotations = gen.report([], [], redefined=True)

    assert "definitions" in text
    assert annotations[0].startswith("::warning::Priority definitions are out of date")


def test_file_round_trip(gen):
    levels = {"virtaal": {"_Find…": "1", "Brackets": "1~", "GNOME": "x"}, "gtk30": {"_Open": "1"}}
    data = gen.to_file(levels, "2026-10-09", RULES)

    assert data["domains"]["virtaal"] == {"1": ["_Find…"], "1~": ["Brackets"], "x": ["GNOME"]}
    assert gen.from_file(data) == levels


def test_level1_refresh_touches_only_level_one(gen):
    committed = {"virtaal": {"_Find…": "1", "Settings": "2", "Gone": "1~", "Old": "3"}}
    candidate = {"virtaal": {"_Find…": "2", "Settings": "3", "New menu item": "1", "Old": "2"}}

    assert gen.level1_refresh(committed, candidate) == {
        "virtaal": {"_Find…": "2", "Settings": "2", "New menu item": "1", "Old": "3"}}


def test_drift_separates_level_one_from_the_rest(gen):
    committed = {"virtaal": {"_Find…": "1", "Settings": "2", "Same": "3"}}
    candidate = {"virtaal": {"_Find…": "1~", "Settings": "3", "Same": "3", "New menu item": "1"}}

    level_one, other = gen.drift(committed, candidate)

    assert level_one == [("virtaal", "New menu item", "?", "1"), ("virtaal", "_Find…", "1", "1~")]
    assert other == [("virtaal", "Settings", "2", "3")]


@pytest.mark.parametrize("key, shown", [
    ("<b>%d</b>", "`<b>%d</b>`"),
    ("Stock label\x04_Open", "`Stock label | _Open`"),
    ("Save?\nYes", "`Save?\\nYes`"),
    ("`code`", "`` `code` ``"),
])
def test_report_shows_messages_as_typed(gen, key, shown):
    # The report is Markdown: markup in a message would render.
    text, _annotations = gen.report([("virtaal", key, "1", "?")], [])

    assert "- virtaal: %s (1 -> ?)" % shown in text


def test_report_warns_only_for_level_one(gen):
    _text, annotations = gen.report([("virtaal", "New menu item", "?", "1")], [("virtaal", "Settings", "2", "3")])

    assert annotations[0].startswith("::warning::Level-1 priorities are out of date")
    assert annotations[1].startswith("::notice::")
    assert gen.report([], [])[1] == []


def test_the_rules_name_only_messages_virtaal_pot_has(gen):
    pytest.importorskip("tomllib")
    assert gen.stale_rules(gen.load_rules(), gen.template_messages()) == []


def test_the_rules_language_codes_are_known(gen):
    pytest.importorskip("tomllib")
    assert gen.apply_names({}, gen.load_rules(), gen.read_linguas())["iso639-3"]["English"] == "1"


def test_written_file_says_its_generated_and_reads_back(gen, tmp_path):
    # YAML 1.1 reads a bare No as false and 1 as a number.
    levels = {"virtaal": {"Stock label\x04_Open": "1", "No": "1~", "Öffnen": "2", "%": "x"}}
    path = tmp_path / "virtaal.priorities.yaml"

    gen.write_file(str(path), gen.to_file(levels, "2026-10-09", RULES))

    assert path.read_text(encoding="utf-8").startswith("# Generated by")
    assert gen.from_file(gen.read_file(str(path))) == levels


def test_an_override_with_a_domain_adds_messages_the_harvest_never_saw(gen):
    rules = dict(RULES, override=RULES["override"] + [
        {"priority": "1", "domain": "gtk-mac-integration", "msgids": ["Quit %s", "Hide Others"]}])

    levels = gen.assign({}, {}, rules)

    assert levels["gtk-mac-integration"] == {"Quit %s": "1", "Hide Others": "1"}


def test_a_domain_override_isnt_checked_against_virtaal_pot(gen):
    rules = {"override": [{"priority": "1", "domain": "gtk-mac-integration", "msgids": ["Quit %s"]}]}

    assert gen.stale_rules(rules, {"_File": ["share/virtaal/virtaal.ui"]}) == []


def test_the_main_window_as_a_file_opens_is_core(gen):
    pytest.importorskip("tomllib")
    rules = gen.load_rules()

    assert gen.sighting_level(rules, "file open", "Window 'vt:quality-checks.po'", "") == "1"
    assert gen.sighting_level(rules, "mode Search", "Window 'vt:quality-checks.po'", "") == "1~"
