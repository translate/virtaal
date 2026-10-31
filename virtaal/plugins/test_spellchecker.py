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
_on_populate_popup, _connect_to_textboxes/destroy) don't touch
main_controller at all - built directly via Plugin.__new__(Plugin) with
just the instance state each one reads, same as the tests above.
"""

from types import SimpleNamespace

import pytest
from gi.repository import GLib, Gtk

from virtaal.common import SignalTracker
from virtaal.common.platform import platform
from virtaal.controllers.baseplugin import PluginUnsupported
from virtaal.plugins import spellchecker
from virtaal.plugins.spellchecker import Plugin


class _FakeEnchant:
    """Records what language code it was actually asked about, without
    needing real enchant/dictionaries installed."""

    def __init__(self, known_dicts):
        self.known_dicts = known_dicts
        self.checked = []

    def dict_exists(self, language):
        self.checked.append(language)
        return language in self.known_dicts


def _text_view(text='', **attrs):
    """A stand-in text view holding text in a real buffer."""
    buffer = Gtk.TextBuffer()
    buffer.set_text(text)
    return SimpleNamespace(get_buffer=lambda: buffer, **attrs)


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

    Plugin._on_unit_lang_changed(plugin, unit_view=None, text_view=SimpleNamespace(), language=language)

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
    text_view = _text_view(spell_pending='en_US')

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
    text_view = _text_view(spell_pending='en_US')

    plugin._activate_checker(text_view, 'en_US')

    assert len(created) == 1
    assert created[0].attached_to is text_view
    assert created[0].language == 'en_US'
    assert created[0].rechecked is True
    assert text_view.spell_lang == 'en_US'


def test_activate_checker_rebinds_gtkspells_domain_after_creating_a_checker(monkeypatch):
    # Every new gtkspell checker binds gtkspell3 to gtkspell's own
    # catalogs, so a lite or pseudo translation of it is only read if
    # bound again after.
    from virtaal.plugins import spellchecker
    rebound = []
    monkeypatch.setattr(spellchecker, 'rebind_library_domain', rebound.append)
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell, _created = _fake_gtkspell(existing=None)

    plugin._activate_checker(_text_view(spell_pending='en_US'), 'en_US')

    assert rebound == [b'gtkspell3']


def test_activate_checker_ignores_a_systemerror_from_get_from_text_view(caplog):
    plugin = Plugin.__new__(Plugin)
    gtkspell, created = _fake_gtkspell(get_from_text_view_raises=SystemError('mandriva'))
    plugin.gtkspell = gtkspell
    text_view = _text_view(spell_pending='en_US')

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
    text_view = _text_view(spell_pending='en_US')

    plugin._activate_checker(text_view, 'en_US')  # must not raise

    assert plugin.gtkspell is None



def _lang_plugin(monkeypatch, known_dicts):
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell, created = _fake_gtkspell(existing=None)
    plugin.enchant = _FakeEnchant(known_dicts=known_dicts)
    plugin._seen_languages = {}
    plugin._enchant_languages = sorted(known_dicts)
    scheduled = []
    monkeypatch.setattr(spellchecker.GLib, 'idle_add', lambda func, *args, **kw: scheduled.append((func, args)))
    return plugin, created, scheduled


def test_a_pending_activation_is_dropped_when_the_language_loses_its_dictionary(monkeypatch):
    # #4441: English was scheduled first; switching to a language with no
    # dictionary yet must not let that pending activation attach English.
    plugin, created, scheduled = _lang_plugin(monkeypatch, {'en_US'})
    text_view = SimpleNamespace()

    plugin._on_unit_lang_changed(None, text_view, 'en')
    plugin._on_unit_lang_changed(None, text_view, 'af')
    for func, args in scheduled:
        func(*args)

    assert created == []
    assert text_view.spell_lang is None


def test_only_the_latest_pending_language_is_activated(monkeypatch):
    plugin, created, scheduled = _lang_plugin(monkeypatch, {'en_US', 'af_ZA'})
    text_view = _text_view()

    plugin._on_unit_lang_changed(None, text_view, 'en')
    plugin._on_unit_lang_changed(None, text_view, 'af')
    for func, args in scheduled:
        func(*args)

    assert [c.language for c in created] == ['af_ZA']
    assert text_view.spell_lang == 'af_ZA'


def _run(scheduled):
    while scheduled:
        func, args = scheduled.pop(0)
        func(*args)


def test_a_large_insert_is_checked_after_it_goes_in(monkeypatch):
    # #4443: GtkSpell checks a long paste word by word against the whole line.
    plugin, created, scheduled = _lang_plugin(monkeypatch, {'en_US'})
    text_view = _text_view()
    plugin._on_unit_lang_changed(None, text_view, 'en')
    _run(scheduled)

    plugin._on_insert_text(text_view.get_buffer(), None, 'x' * spellchecker.LARGE_INSERT, -1, text_view)

    assert text_view.spell_lang is None
    assert [func for func, _ in scheduled] == [plugin._activate_checker]


def test_a_small_insert_is_left_to_gtkspell(monkeypatch):
    plugin, created, scheduled = _lang_plugin(monkeypatch, {'en_US'})
    text_view = _text_view()
    plugin._on_unit_lang_changed(None, text_view, 'en')
    _run(scheduled)

    plugin._on_insert_text(text_view.get_buffer(), None, 'word', -1, text_view)

    assert text_view.spell_lang == 'en_US'
    assert scheduled == []


def test_text_with_a_very_long_line_is_not_checked(monkeypatch):
    plugin, created, scheduled = _lang_plugin(monkeypatch, {'en_US'})
    text_view = _text_view('short\n' + 'x' * (spellchecker.LONGEST_CHECKED_LINE + 1))

    plugin._on_unit_lang_changed(None, text_view, 'en')
    _run(scheduled)

    assert created == []
    assert text_view.spell_lang is None


def test_many_lines_of_a_long_text_are_checked(monkeypatch):
    plugin, created, scheduled = _lang_plugin(monkeypatch, {'en_US'})
    text_view = _text_view('word\n' * spellchecker.LONGEST_CHECKED_LINE)

    plugin._on_unit_lang_changed(None, text_view, 'en')
    _run(scheduled)

    assert text_view.spell_lang == 'en_US'


@pytest.mark.parametrize('edit', ['insert', 'delete'])
def test_checking_resumes_once_the_long_line_is_gone(monkeypatch, edit):
    plugin, created, scheduled = _lang_plugin(monkeypatch, {'en_US'})
    text_view = _text_view('x' * (spellchecker.LONGEST_CHECKED_LINE + 1))
    buffer = text_view.get_buffer()
    plugin._on_unit_lang_changed(None, text_view, 'en')
    _run(scheduled)

    buffer.set_text('short')
    if edit == 'insert':
        plugin._on_insert_text(buffer, None, 'a', -1, text_view)
    else:
        plugin._on_delete_range(buffer, None, None, text_view)
    _run(scheduled)

    assert text_view.spell_lang == 'en_US'


def test_an_insert_doesnt_turn_checking_back_on_once_disabled(monkeypatch):
    plugin, created, scheduled = _lang_plugin(monkeypatch, {'en_US'})
    text_view = _text_view()
    plugin._on_unit_lang_changed(None, text_view, 'en')
    _run(scheduled)
    plugin._disable_checking(text_view)

    plugin._on_insert_text(text_view.get_buffer(), None, 'x' * spellchecker.LARGE_INSERT, -1, text_view)

    assert scheduled == []
    assert text_view.spell_lang is None


@pytest.mark.parametrize('text,expected', [
    ('', 0),
    ('ab\ncde', 3),
    ('ab\r\ncde', 3),
    ('ab\rcde', 3),
    ('ab\u2029cde', 3),
    # Not a line end in a GtkTextBuffer.
    ('ab\u2028cde', 6),
])
def test_longest_line_splits_where_a_text_buffer_does(text, expected):
    buffer = Gtk.TextBuffer()
    buffer.set_text(text)

    assert spellchecker._longest_line(buffer) == expected


def test_activate_checker_sets_the_language_before_attaching():
    # #4439: attaching a checker with no language yet rechecked the text
    # without a speller ('speller != NULL' criticals).
    order = []

    class _Checker(_FakeChecker):
        get_from_text_view = staticmethod(lambda tv: None)

        def set_language(self, language):
            order.append('set_language')
            super().set_language(language)

        def attach(self, text_view):
            order.append('attach')
            super().attach(text_view)

    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = SimpleNamespace(Checker=_Checker)

    plugin._activate_checker(_text_view(spell_pending='en_US'), 'en_US')

    assert order == ['set_language', 'attach']



def test_activate_checker_leaves_nothing_attached_when_set_language_fails():
    class _Checker(_FakeChecker):
        get_from_text_view = staticmethod(lambda tv: None)

        def set_language(self, language):
            raise RuntimeError('no dictionary')

    attached = []
    _Checker.attach = lambda self, text_view: attached.append(text_view)
    plugin = Plugin.__new__(Plugin)
    plugin.gtkspell = SimpleNamespace(Checker=_Checker)

    plugin._activate_checker(_text_view(spell_pending='en_US'), 'en_US')

    assert attached == []


# _on_populate_popup() #

def _menu_with(*labels_or_separator):
    """A real Gtk.Menu, populated with real Gtk.MenuItems for each label
    (or a real Gtk.SeparatorMenuItem for the literal `None`)."""
    menu = Gtk.Menu()
    for label in labels_or_separator:
        item = Gtk.SeparatorMenuItem() if label is None else Gtk.MenuItem(label=label)
        menu.append(item)
    return menu


def test_fix_menu_removes_an_exact_languages_match():
    menu = _menu_with('Languages')
    plugin = Plugin.__new__(Plugin)

    plugin._on_populate_popup(textbox=Gtk.TextView(), menu=menu)

    assert menu.get_children() == []


def test_fix_menu_removes_a_translated_languages_item(monkeypatch):
    # gtkspell shows "Languages" from its own gtkspell3 catalog, so a
    # translated UI only matches through that same domain.
    from virtaal.plugins import spellchecker
    monkeypatch.setattr(spellchecker.GLib, 'dgettext',
                        lambda domain, msgid: 'Tale' if (domain, msgid) == ('gtkspell3', 'Languages') else msgid)
    menu = _menu_with('Ignore All', 'Tale')
    plugin = Plugin.__new__(Plugin)

    plugin._on_populate_popup(textbox=Gtk.TextView(), menu=menu)

    assert [item.get_property('label') for item in menu.get_children()] == ['Ignore All']


def test_fix_menu_keeps_a_label_that_is_only_a_substring_of_languages():
    # Regression: `label in dgettext(...)` did a substring check rather
    # than comparing the whole label, so a short label like "an" was
    # wrongly removed too ("an" is a substring of "Languages").
    menu = _menu_with('an')
    plugin = Plugin.__new__(Plugin)

    plugin._on_populate_popup(textbox=Gtk.TextView(), menu=menu)

    assert len(menu.get_children()) == 1


def test_fix_menu_stops_at_the_first_separator():
    menu = _menu_with('Ignore All', None, 'Languages')
    plugin = Plugin.__new__(Plugin)

    plugin._on_populate_popup(textbox=Gtk.TextView(), menu=menu)

    # The separator had real entries before it, so it's kept, and
    # everything after it - including "Languages" - is never reached.
    remaining = menu.get_children()
    assert len(remaining) == 3
    assert remaining[1].get_name() == 'GtkSeparatorMenuItem'
    assert remaining[2].get_property('label') == 'Languages'


def _read_only_textview():
    textview = Gtk.TextView()
    textview.set_editable(False)
    return textview


def test_fix_menu_offers_no_suggestions_for_read_only_source_text(monkeypatch):
    from virtaal.plugins import spellchecker
    monkeypatch.setattr(spellchecker.GLib, 'dgettext', lambda domain, msgid: msgid)
    # gtkspell's items come before the text view's own, up to a separator
    menu = _menu_with('The', 'More...', 'Add "virtaal" to Dictionary', 'Ignore All', 'Languages', None, 'Copy')
    plugin = Plugin.__new__(Plugin)

    plugin._on_populate_popup(textbox=_read_only_textview(), menu=menu)

    assert [item.get_label() for item in menu.get_children()] == [
        'Add "virtaal" to Dictionary',
        'Ignore All',
        '',
        'Copy',
    ]


def test_fix_menu_keeps_translated_dictionary_items_for_read_only_text(monkeypatch):
    from virtaal.plugins import spellchecker
    translations = {'Ignore All': 'Ignoreer almal', 'Add "%s" to Dictionary': 'Voeg "%s" by die woordeboek'}
    monkeypatch.setattr(spellchecker.GLib, 'dgettext', lambda domain, msgid: translations.get(msgid, msgid))
    menu = _menu_with('The', 'Voeg "virtaal" by die woordeboek', 'Ignoreer almal', None, 'Copy')
    plugin = Plugin.__new__(Plugin)

    plugin._on_populate_popup(textbox=_read_only_textview(), menu=menu)

    assert [item.get_label() for item in menu.get_children()][:2] == [
        'Voeg "virtaal" by die woordeboek',
        'Ignoreer almal',
    ]


def test_fix_menu_keeps_suggestions_for_editable_text():
    menu = _menu_with('The', 'More...', None, 'Ignore All')
    plugin = Plugin.__new__(Plugin)

    plugin._on_populate_popup(textbox=Gtk.TextView(), menu=menu)

    assert [item.get_property('label') for item in menu.get_children()][:2] == ['The', 'More...']


def test_fix_menu_removes_a_leading_separator_with_nothing_before_it():
    menu = _menu_with(None, 'Ignore All')
    plugin = Plugin.__new__(Plugin)

    plugin._on_populate_popup(textbox=Gtk.TextView(), menu=menu)

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


def test_connect_to_textboxes_runs_after_other_populate_popup_handlers():
    # Regression: connected as a normal (before-phase) handler, ours used
    # to run before gtkspell's own populate-popup handler ever added
    # "Languages" - forcing a reactive remove-after-show that couldn't
    # cleanly shrink the already-displayed popup. connect_after ensures
    # ours runs last, so removal happens before the menu is ever shown.
    plugin = Plugin.__new__(Plugin)
    plugin._signal_tracker = SignalTracker()
    order = []
    plugin._on_populate_popup = lambda textbox, menu: order.append('spellchecker')
    textbox = Gtk.TextView()
    textbox.connect('populate-popup', lambda *a: order.append('other-plugin'))

    plugin._connect_to_textboxes(unitview=None, textboxes=[textbox])
    textbox.emit('populate-popup', Gtk.Menu())

    assert order == ['other-plugin', 'spellchecker']


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


def test_a_text_view_without_placeables_has_its_words_checked():
    text_view = Gtk.TextView()
    text_view.get_buffer().set_text('renamd')
    start, end = text_view.get_buffer().get_bounds()

    assert not spellchecker._in_placeable(text_view, start, end)


def test_unsupported_in_a_frozen_build(monkeypatch):
    """The Windows and macOS builds don't bundle a version-matched
    gtkspell3 - a system-found one can mismatch the frozen app's own
    bundled GTK3 and crash outright."""
    monkeypatch.setattr(platform, 'is_frozen', True)
    monkeypatch.setattr(platform, 'is_appimage', False)
    with pytest.raises(PluginUnsupported, match='frozen'):
        Plugin('spellchecker', None)


def test_appimage_passes_the_frozen_build_check(monkeypatch):
    """The AppImage bundles gtkspell3 with its own GTK."""
    try:
        import gi
        gi.require_version('GtkSpell', '3.0')
        from gi.repository import GtkSpell  # noqa: F401
    except (ImportError, ValueError):
        pytest.skip("GtkSpell 3.0 typelib not installed - optional")
    monkeypatch.setattr(platform, 'is_frozen', True)
    monkeypatch.setattr(platform, 'is_appimage', True)
    monkeypatch.setattr(platform, 'is_windows', False)
    # Stops the plugin before it needs a main_controller.
    monkeypatch.setattr(spellchecker, 'import_enchant', lambda: None)

    with pytest.raises(PluginUnsupported, match='pyenchant'):
        Plugin('spellchecker', None)


def test_unsupported_on_windows_with_a_non_ascii_username(monkeypatch):
    monkeypatch.setattr(platform, 'is_frozen', False)
    monkeypatch.setattr(platform, 'is_windows', True)
    monkeypatch.setenv('APPDATA', 'C:\\Users\\\u00e9lise\\AppData\\Roaming')

    with pytest.raises(PluginUnsupported):
        Plugin('spellchecker', None)


def test_unsupported_without_gtkspell(monkeypatch):
    """The GtkSpell typelib isn't always installed."""
    import gi
    require_version = gi.require_version

    def missing_gtkspell(namespace, version):
        if namespace == 'GtkSpell':
            raise ValueError('Namespace GtkSpell not available')
        return require_version(namespace, version)
    monkeypatch.setattr(gi, 'require_version', missing_gtkspell)
    monkeypatch.setattr(platform, 'is_frozen', False)
    monkeypatch.setattr(platform, 'is_windows', False)

    with pytest.raises(PluginUnsupported, match='GtkSpell'):
        Plugin('spellchecker', None)


def test_unsupported_without_a_usable_enchant(monkeypatch):
    """#4313: a leftover "enchant" directory isn't pyenchant."""
    try:
        import gi
        gi.require_version('GtkSpell', '3.0')
        from gi.repository import GtkSpell  # noqa: F401
    except (ImportError, ValueError):
        pytest.skip("GtkSpell 3.0 typelib not installed - optional")
    monkeypatch.setattr(platform, 'is_frozen', False)
    monkeypatch.setattr(platform, 'is_windows', False)
    monkeypatch.setattr(spellchecker, 'import_enchant', lambda: None)

    with pytest.raises(PluginUnsupported, match='pyenchant'):
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


def test_gtkspells_iso_codes_warnings_are_dropped(monkeypatch):
    # #4448: GtkSpell warns that it can't find iso-codes on macOS.
    passed = []
    monkeypatch.setattr(GLib, 'log_default_handler', lambda *args: passed.append(args[2]))
    for message in ('iso_639.xml: Failed to open file', 'iso_3166.xml: Failed to open file', 'Something else'):
        spellchecker._NoIsoCodesWarnings._log('', GLib.LogLevelFlags.LEVEL_WARNING, message)

    assert passed == ['Something else']


def test_the_iso_codes_filter_is_removed_afterwards(monkeypatch):
    calls = []
    monkeypatch.setattr(GLib, 'log_set_handler', lambda *args: calls.append(('set', args[0])) or 7)
    monkeypatch.setattr(GLib, 'log_remove_handler', lambda *args: calls.append(('remove',) + args))

    with spellchecker._NoIsoCodesWarnings():
        pass

    assert calls == [('set', ''), ('remove', '', 7)]


def test_a_downloaded_dictionary_is_checked_without_a_restart(monkeypatch):
    # #4585: a language remembered as having no dictionary stayed unchecked.
    plugin, created, scheduled = _lang_plugin(monkeypatch, set())
    target = _text_view()
    plugin.unit_view = SimpleNamespace(sources=[], targets=[target])
    plugin._on_unit_lang_changed(None, target, 'af')
    assert plugin._seen_languages == {'af': None}

    plugin.enchant.known_dicts.add('af_ZA')
    plugin.enchant.list_languages = lambda: ['af_ZA']
    lang_controller = SimpleNamespace(source_lang=SimpleNamespace(code='en'), target_lang=SimpleNamespace(code='af'))
    plugin._on_dictionary_installed(lang_controller, 'af_ZA')
    _run(scheduled)

    assert target.spell_lang == 'af_ZA'
