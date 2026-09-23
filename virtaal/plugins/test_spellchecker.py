#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Tests for the spellchecker plugin.

These mostly avoid instantiating virtaal.plugins.spellchecker.Plugin
itself, since __init__ needs a full MainController/GTK unit view - out of
reach for a plain unit test. What's covered instead: the plugin's
dependency-free helper logic, and a regression check for the fix landed in
commit 7663e3e9 (the plugin silently failing to load because pyenchant was
never installed, not because of any GTK2/GTK3 incompatibility). The one
exception is the frozen-build check below, which is guaranteed to raise
before __init__ ever touches main_controller.

The rest of the methods (_disable_checking, _activate_checker,
_on_populate_popup/_fix_menu, _connect_to_textboxes/destroy) don't touch
main_controller at all - built directly via Plugin.__new__(Plugin) with
just the instance state each one reads, same as the tests above.
"""

from types import SimpleNamespace

import pytest
from gi.repository import GLib, Gtk

from virtaal.common import SignalTracker
from virtaal.common.platform import platform
from virtaal.controllers.baseplugin import PluginUnsupported
from virtaal.plugins.spellchecker import Plugin, _dict_add_re


class _FakeEnchant:
    """Records what language code it was actually asked about, without
    needing real enchant/dictionaries installed."""

    def __init__(self, known_dicts):
        self.known_dicts = known_dicts
        self.checked = []

    def dict_exists(self, language):
        self.checked.append(language)
        return language in self.known_dicts


class _FakeChecker:
    """Stands in for a real gtkspell.Checker instance."""

    def __init__(self):
        self.language = None
        self.rechecked = False
        self.attached_to = None
        self.detached = False

    def attach(self, text_view):
        self.attached_to = text_view

    def detach(self):
        self.detached = True

    def set_language(self, language):
        self.language = language

    def recheck_all(self):
        self.rechecked = True


def _fake_gtkspell(existing=None, get_from_text_view_raises=None):
    """A stand-in for the `gtkspell` module: `.Checker` needs to work
    both as a callable constructor and as the type
    `.Checker.get_from_text_view(...)` is a static method on."""
    created = []

    class _Checker(_FakeChecker):
        def __init__(self):
            super().__init__()
            created.append(self)

    def get_from_text_view(text_view):
        if get_from_text_view_raises:
            raise get_from_text_view_raises
        return existing

    _Checker.get_from_text_view = staticmethod(get_from_text_view)
    return SimpleNamespace(Checker=_Checker), created


def test_dict_add_re_matches_gtkspell_suggestion():
    """_dict_add_re extracts the word from GtkSpell's context-menu label
    ('Add "x" to Dictionary'), which _fix_menu() then re-translates."""
    m = _dict_add_re.match('Add "virtaal" to Dictionary')
    assert m is not None
    assert m.group(1) == "virtaal"


def test_dict_add_re_no_match_on_unrelated_label():
    assert _dict_add_re.match("Ignore All") is None


@pytest.mark.parametrize("language,expected", [("pt", "pt_PT"), ("de", "de_DE")])
def test_on_unit_lang_changed_maps_to_country_variant(language, expected):
    """Regression: a `==` vs `=` typo made these branches no-ops, so 'pt'
    and 'de' were probed against enchant as themselves instead of the
    country variant, the same treatment 'en' already got correctly."""
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = object()
    plugin.enchant = _FakeEnchant(known_dicts={expected})
    plugin._seen_languages = {}
    plugin._enchant_languages = []

    Plugin._on_unit_lang_changed(plugin, unit_view=None, text_view=None, language=language)

    assert plugin.enchant.checked == [expected]


def test_on_unit_lang_changed_does_nothing_once_gtkspell_is_gone():
    # _activate_checker() sets gtkspell to None on an unexpected error -
    # every later call for this text view must stay a no-op from then on.
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = None

    Plugin._on_unit_lang_changed(plugin, unit_view=None, text_view=None, language='en')  # must not raise


def test_on_unit_lang_changed_reuses_a_previously_seen_country_variant():
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = object()
    plugin.enchant = _FakeEnchant(known_dicts=set())
    plugin._seen_languages = {'xx': 'xx_YY'}
    plugin._enchant_languages = []
    text_view = SimpleNamespace()

    with pytest.MonkeyPatch.context() as mp:
        calls = []
        mp.setattr(GLib, 'idle_add', lambda *a, **k: calls.append((a, k)))
        Plugin._on_unit_lang_changed(plugin, unit_view=None, text_view=text_view, language='xx')

    # Already resolved once, so enchant is never re-asked about 'xx' itself.
    assert plugin.enchant.checked == []
    assert calls == [((plugin._activate_checker, text_view, 'xx_YY'), {'priority': GLib.PRIORITY_LOW})]


def test_on_unit_lang_changed_finds_a_country_variant_enchant_supports():
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = object()
    plugin.enchant = _FakeEnchant(known_dicts=set())
    plugin._seen_languages = {}
    plugin._enchant_languages = ['xx_YY']
    text_view = SimpleNamespace()

    with pytest.MonkeyPatch.context() as mp:
        calls = []
        mp.setattr(GLib, 'idle_add', lambda *a, **k: calls.append((a, k)))
        Plugin._on_unit_lang_changed(plugin, unit_view=None, text_view=text_view, language='xx')

    assert plugin._seen_languages['xx'] == 'xx_YY'
    assert calls == [((plugin._activate_checker, text_view, 'xx_YY'), {'priority': GLib.PRIORITY_LOW})]


def test_on_unit_lang_changed_disables_and_caches_a_language_with_no_dictionary(monkeypatch):
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = object()
    plugin.enchant = _FakeEnchant(known_dicts=set())
    plugin._seen_languages = {}
    plugin._enchant_languages = []
    disabled = []
    monkeypatch.setattr(plugin, '_disable_checking', lambda tv: disabled.append(tv))
    text_view = SimpleNamespace()

    Plugin._on_unit_lang_changed(plugin, unit_view=None, text_view=text_view, language='zz')

    assert disabled == [text_view]
    assert plugin._seen_languages['zz'] is None


def test_on_unit_lang_changed_disables_for_a_language_cached_as_unavailable(monkeypatch):
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = object()
    plugin.enchant = _FakeEnchant(known_dicts=set())
    plugin._seen_languages = {'zz': None}
    plugin._enchant_languages = []
    disabled = []
    monkeypatch.setattr(plugin, '_disable_checking', lambda tv: disabled.append(tv))
    text_view = SimpleNamespace()

    Plugin._on_unit_lang_changed(plugin, unit_view=None, text_view=text_view, language='zz')

    assert disabled == [text_view]
    # A previously-failed lookup is trusted from the cache - enchant isn't
    # asked about it again.
    assert plugin.enchant.checked == []


def test_on_unit_lang_changed_skips_an_already_active_language():
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = object()
    plugin.enchant = _FakeEnchant(known_dicts={'en_US'})
    plugin._seen_languages = {}
    plugin._enchant_languages = []
    text_view = SimpleNamespace(spell_lang='en_US')

    with pytest.MonkeyPatch.context() as mp:
        calls = []
        mp.setattr(GLib, 'idle_add', lambda *a, **k: calls.append((a, k)))
        Plugin._on_unit_lang_changed(plugin, unit_view=None, text_view=text_view, language='en')

    assert calls == []


# _disable_checking() #

def test_disable_checking_is_a_noop_when_already_disabled():
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = SimpleNamespace(Checker=SimpleNamespace(
        get_from_text_view=lambda tv: pytest.fail('should not be called')))
    text_view = SimpleNamespace(spell_lang=None)

    plugin._disable_checking(text_view)  # must not raise


def test_disable_checking_detaches_an_active_checker():
    plugin = Plugin.__new__(Plugin)
    gtkspell, _created = _fake_gtkspell()
    checker = _FakeChecker()
    gtkspell.Checker.get_from_text_view = staticmethod(lambda tv: checker)
    plugin.gtkspell = gtkspell
    text_view = SimpleNamespace()  # no spell_lang attr yet

    plugin._disable_checking(text_view)

    assert checker.detached is True
    assert text_view.spell_lang is None


def test_disable_checking_handles_no_active_checker():
    plugin = Plugin.__new__(Plugin)
    gtkspell, _created = _fake_gtkspell(existing=None)
    plugin.gtkspell = gtkspell
    text_view = SimpleNamespace()

    plugin._disable_checking(text_view)  # must not raise

    assert text_view.spell_lang is None


def test_disable_checking_ignores_a_systemerror_from_get_from_text_view(caplog):
    # Regression: this used to re-raise via a stray `raise e` that
    # contradicted its own comment (and _activate_checker's identical
    # comment on the equivalent branch, which really does swallow it).
    plugin = Plugin.__new__(Plugin)
    gtkspell, _created = _fake_gtkspell(get_from_text_view_raises=SystemError('mandriva'))
    plugin.gtkspell = gtkspell
    text_view = SimpleNamespace()

    with caplog.at_level('DEBUG'):
        plugin._disable_checking(text_view)  # must not raise

    assert text_view.spell_lang is None
    # Swallowed, but not silently - still logged for anyone debugging.
    assert 'mandriva' in caplog.text


# _activate_checker() #

def test_activate_checker_reuses_an_existing_checker():
    existing = _FakeChecker()
    plugin = Plugin.__new__(Plugin)
    gtkspell, created = _fake_gtkspell(existing=existing)
    plugin.gtkspell = gtkspell
    text_view = SimpleNamespace()

    plugin._activate_checker(text_view, 'en_US')

    assert created == []  # reused, never constructed a new one
    assert existing.attached_to is None  # ... and so never (re)attached either
    assert existing.language == 'en_US'
    assert existing.rechecked is True
    assert text_view.spell_lang == 'en_US'


def test_activate_checker_creates_and_attaches_a_new_checker_when_none_exists():
    plugin = Plugin.__new__(Plugin)
    gtkspell, created = _fake_gtkspell(existing=None)
    plugin.gtkspell = gtkspell
    text_view = SimpleNamespace()

    plugin._activate_checker(text_view, 'en_US')

    assert len(created) == 1
    assert created[0].attached_to is text_view
    assert created[0].language == 'en_US'
    assert created[0].rechecked is True
    assert text_view.spell_lang == 'en_US'


def test_activate_checker_ignores_a_systemerror_from_get_from_text_view(caplog):
    plugin = Plugin.__new__(Plugin)
    gtkspell, created = _fake_gtkspell(get_from_text_view_raises=SystemError('mandriva'))
    plugin.gtkspell = gtkspell
    text_view = SimpleNamespace()

    with caplog.at_level('DEBUG'):
        plugin._activate_checker(text_view, 'en_US')  # must not raise

    assert len(created) == 1
    assert text_view.spell_lang == 'en_US'
    assert 'mandriva' in caplog.text


def test_activate_checker_disables_the_plugin_on_an_unexpected_error():
    class _BrokenChecker:
        get_from_text_view = staticmethod(lambda tv: None)

        def __init__(self):
            raise RuntimeError('boom')

    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = SimpleNamespace(Checker=_BrokenChecker)
    text_view = SimpleNamespace()

    plugin._activate_checker(text_view, 'en_US')  # must not raise

    assert plugin.gtkspell is None


# _on_populate_popup() #

def test_on_populate_popup_schedules_fix_menu(monkeypatch):
    calls = []
    monkeypatch.setattr(GLib, 'idle_add', lambda *a, **k: calls.append((a, k)))
    plugin = Plugin.__new__(Plugin)
    menu = object()

    plugin._on_populate_popup(textbox=None, menu=menu)

    assert calls == [((plugin._fix_menu, menu), {})]


# _fix_menu() #

def _menu_with(*labels_or_separator):
    """A real Gtk.Menu, populated with real Gtk.MenuItems for each label
    (or a real Gtk.SeparatorMenuItem for the literal `None`)."""
    menu = Gtk.Menu()
    for label in labels_or_separator:
        item = Gtk.SeparatorMenuItem() if label is None else Gtk.MenuItem(label=label)
        menu.append(item)
    return menu


def test_fix_menu_translates_known_gtkspell_labels(monkeypatch):
    # NullTranslations (installed for every test) makes _() an identity
    # function, so a translated and untranslated label are the same
    # string - marking _() distinctly is the only way to tell the
    # branch actually ran.
    monkeypatch.setattr('builtins._', lambda s: s + '!!')
    menu = _menu_with('<i>(no suggestions)</i>', 'Ignore All', 'More...', 'Add "virtaal" to Dictionary')
    plugin = Plugin.__new__(Plugin)

    plugin._fix_menu(menu)

    labels = [item.get_property('label') for item in menu]
    assert labels == [
        '<i>(no suggestions)</i>!!',
        'Ignore All!!',
        'More…!!',
        'Add "virtaal" to Dictionary!!',
    ]


def test_fix_menu_removes_an_exact_languages_match():
    menu = _menu_with('Languages')
    plugin = Plugin.__new__(Plugin)

    plugin._fix_menu(menu)

    assert menu.get_children() == []


def test_fix_menu_keeps_a_label_that_is_only_a_substring_of_languages():
    # Regression: `label in dgettext(...)` did a substring check rather
    # than comparing the whole label, so a short label like "an" was
    # wrongly removed too (dgettext('gtkspell', 'Languages') returns the
    # untranslated literal "Languages" here, and "an" is a substring of it).
    menu = _menu_with('an')
    plugin = Plugin.__new__(Plugin)

    plugin._fix_menu(menu)

    assert len(menu.get_children()) == 1


def test_fix_menu_stops_at_the_first_separator():
    menu = _menu_with('Ignore All', None, 'Languages')
    plugin = Plugin.__new__(Plugin)

    plugin._fix_menu(menu)

    # The separator had real entries before it, so it's kept, and
    # everything after it - including "Languages" - is never reached.
    remaining = menu.get_children()
    assert len(remaining) == 3
    assert remaining[1].get_name() == 'GtkSeparatorMenuItem'
    assert remaining[2].get_property('label') == 'Languages'


def test_fix_menu_removes_a_leading_separator_with_nothing_before_it():
    menu = _menu_with(None, 'Ignore All')
    plugin = Plugin.__new__(Plugin)

    plugin._fix_menu(menu)

    remaining = menu.get_children()
    assert len(remaining) == 1
    assert remaining[0].get_name() != 'GtkSeparatorMenuItem'


# _connect_to_textboxes() / destroy() #

def test_connect_to_textboxes_wires_populate_popup():
    plugin = Plugin.__new__(Plugin)
    plugin._signal_tracker = SignalTracker()
    fix_menu_calls = []
    plugin._on_populate_popup = lambda textbox, menu: fix_menu_calls.append((textbox, menu))
    textbox = Gtk.TextView()

    plugin._connect_to_textboxes(unitview=None, textboxes=[textbox])
    textbox.emit('populate-popup', Gtk.Menu())

    assert len(fix_menu_calls) == 1
    assert fix_menu_calls[0][0] is textbox


def test_destroy_disconnects_signals_and_disables_every_textview():
    plugin = Plugin.__new__(Plugin)
    plugin._signal_tracker = SignalTracker()
    source = Gtk.TextView()
    target = Gtk.TextView()
    plugin.unit_view = SimpleNamespace(sources=[source], targets=[target])
    disabled = []
    plugin._disable_checking = lambda tv: disabled.append(tv)
    tracked = Gtk.TextView()
    plugin._signal_tracker.connect(tracked, 'populate-popup', lambda *a: None)

    plugin.destroy()

    assert disabled == [source, target]
    assert plugin._signal_tracker._ids == []


def test_unsupported_in_any_frozen_build(monkeypatch):
    """A frozen build never bundles a version-matched gtkspell3 - a
    system-found one can mismatch the frozen app's own bundled GTK3
    and crash outright."""
    monkeypatch.setattr(platform, 'is_frozen', True)
    with pytest.raises(PluginUnsupported):
        Plugin('spellchecker', None)


def test_unsupported_on_windows_with_a_non_ascii_username(monkeypatch):
    monkeypatch.setattr(platform, 'is_frozen', False)
    monkeypatch.setattr(platform, 'is_windows', True)
    monkeypatch.setenv('APPDATA', 'C:\\Users\\\u00e9lise\\AppData\\Roaming')

    with pytest.raises(PluginUnsupported):
        Plugin('spellchecker', None)


def test_spellchecker_dependencies_importable():
    """enchant and GtkSpell 3.0 must both be importable, and enchant must
    report at least one available dictionary/provider, for the
    spellchecker plugin to load at all.

    Skips (rather than fails) when these optional system dependencies
    aren't installed, since the plugin is designed to degrade gracefully
    without them. CI always installs them (.github/workflows/ci.yml), so
    this is a real, enforced check there rather than a permanent skip.
    """
    try:
        import enchant
    except ImportError:
        pytest.skip("pyenchant not installed - optional")

    try:
        import gi
        gi.require_version("GtkSpell", "3.0")
        from gi.repository import GtkSpell  # noqa: F401
    except (ImportError, ValueError):
        pytest.skip("GtkSpell 3.0 typelib not installed - optional")

    assert enchant.list_languages(), (
        "enchant imported but reports no available dictionaries/providers "
        "- check the enchant backend (hunspell/aspell) is installed"
    )
