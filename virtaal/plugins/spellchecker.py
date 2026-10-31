#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
import os
import os.path
import re

from gi.repository import GLib

from virtaal.common import SignalTracker
from virtaal.common.platform import platform
from virtaal.controllers.baseplugin import BasePlugin, PluginUnsupported
from virtaal.support.enchant_compat import enchant_tag, import_enchant
from virtaal.support.libi18n.locale import rebind_library_domain


def _gtkspell_text(msgid):
    """gtkspell's own translation of msgid, kept out of virtaal.pot."""
    return GLib.dgettext('gtkspell3', msgid)


def _is_dictionary_entry(label):
    """Whether a gtkspell menu item changes only the dictionary, not the text."""
    if label == _gtkspell_text('Ignore All'):
        return True
    add = re.escape(_gtkspell_text('Add "%s" to Dictionary')).replace('%s', '.*')
    return re.fullmatch(add, label) is not None


def _in_placeable(textbox, start, end):
    """Whether the text from C{start} to C{end} is in a placeable that
        isn't translated, such as a variable."""
    gui_info = getattr(getattr(textbox, 'elem', None), 'gui_info', None)
    if gui_info is None:
        return False
    for offset in (start.get_offset(), end.get_offset() - 1):
        elem = gui_info.elem_at_offset(offset)
        if elem is not None and not elem.istranslatable:
            return True
    return False


class Plugin(BasePlugin):
    """A plugin to control spell checking."""

    display_name = _('Spell Checker')
    description = _('Check spelling and provide suggestions')
    version = 0.1

    # INITIALIZERS #
    def __init__(self, internal_name, main_controller):
        self.internal_name = internal_name

        if platform.is_frozen and not platform.is_appimage:
            # No version-matched gtkspell3 bundled yet (UI-stage work) -
            # a frozen build must never trust a system-found one: a
            # mismatched GTK3 copy crashes outright (GTK_IS_TEXT_VIEW
            # assertion, ObjC duplicate-class registration) rather than
            # just failing to import. The AppImage bundles the
            # gtkspell3 built against its own GTK.
            raise PluginUnsupported("gtkspell3 isn't bundled in a frozen build")

        if platform.is_windows:
            DICTDIR = os.path.join(os.environ['APPDATA'], 'enchant', 'myspell')
            # DICTDIR is already str (unicode text) under Python 3, so there's
            # nothing to decode - .decode() doesn't exist on str at all and
            # raised AttributeError unconditionally here. The original intent
            # (enchant won't work on Windows with a non-ascii path) still
            # applies though, so check encodability instead of decoding.
            try:
                DICTDIR.encode('ascii')
            except UnicodeEncodeError:
                raise PluginUnsupported("Spell checking is not supported with non-ascii username")

        # If these imports fail, the plugin is automatically disabled -
        # gi.require_version() raises ValueError (not ImportError) when
        # the typelib itself is simply missing (true for this project's
        # gvsbuild GTK3 build, which doesn't ship GtkSpell/enchant at
        # all), so both need catching here, not just ImportError.
        try:
            import gi
            gi.require_version('GtkSpell', '3.0')
            from gi.repository import GtkSpell as gtkspell
        except (ImportError, ValueError) as e:
            raise PluginUnsupported(str(e))
        enchant = import_enchant()
        if enchant is None:
            raise PluginUnsupported("pyenchant isn't installed")
        self.gtkspell = gtkspell
        self.enchant = enchant
        # languages that we've handled before:
        self._seen_languages = {}
        # languages supported by enchant:
        self._enchant_languages = self.enchant.list_languages()

        unit_view = main_controller.unit_controller.view
        self.unit_view = unit_view
        self._signal_tracker = SignalTracker()
        self._signal_tracker.connect(self.unit_view, 'textview-language-changed', self._on_unit_lang_changed)

        # For some reason the i18n of gtkspell doesn't work on Windows, so we
        # intervene. We also don't want the Languages submenu, so we remove it.
        if unit_view.sources:
            self._connect_to_textboxes(unit_view, unit_view.sources)
            srclang = main_controller.lang_controller.source_lang.code
            for textview in unit_view.sources:
                self._on_unit_lang_changed(unit_view, textview, srclang)
        else:
            self._signal_tracker.connect(unit_view, 'sources-created', self._connect_to_textboxes)
        if unit_view.targets:
            self._connect_to_textboxes(unit_view, unit_view.targets)
            tgtlang = main_controller.lang_controller.target_lang.code
            for textview in unit_view.targets:
                self._on_unit_lang_changed(unit_view, textview, tgtlang)
        else:
            self._signal_tracker.connect(unit_view, 'targets-created', self._connect_to_textboxes)

    def destroy(self):
        """Remove signal connections and disable spell checking."""
        self._signal_tracker.disconnect_all()
        for text_view in self.unit_view.sources + self.unit_view.targets:
            self._disable_checking(text_view)

    def _connect_to_textboxes(self, unitview, textboxes):
        for textbox in textboxes:
            # after=True: gtkspell (and the other populate-popup plugins)
            # connect normally and build their items synchronously in the
            # same emission - running after them means "Languages" can be
            # removed before the menu is ever shown, instead of shrinking
            # an already-visible popup (which GTK doesn't support cleanly).
            self._signal_tracker.connect(textbox, 'populate-popup', self._on_populate_popup, after=True)
            self._signal_tracker.connect(textbox.get_buffer(), 'apply-tag', self._on_apply_tag, textbox)


    # METHODS #

    def _disable_checking(self, text_view):
        """Disable checking on the given text_view."""
        # Drop any activation still waiting to run (#4441).
        text_view.spell_pending = None
        if getattr(text_view, 'spell_lang', 'xxxx') is None:
            # No change necessary - already disabled
            return
        spell = None
        try:
            spell = self.gtkspell.Checker.get_from_text_view(text_view)
        except SystemError as e:
            # At least on Mandriva .get_from_text_view() sometimes returns
            # a SystemError without a description. Things seem to work fine
            # anyway, so let's ignore it and hope for the best.
            logging.debug("gtkspell.Checker.get_from_text_view() raised: %s", e)
        if not spell is None:
            spell.detach()
        text_view.spell_lang = None


    # SIGNAL HANDLERS #
    def _on_unit_lang_changed(self, unit_view, text_view, language):
        if not self.gtkspell:
            return

        # enchant doesn't like anything except plain strings (bug 1852)
        language = str(language)

        if language == 'en':
            language = 'en_US'
        elif language == 'pt':
            language = 'pt_PT'
        elif language == 'de':
            language = 'de_DE'
        language = enchant_tag(language)

        if not language in self._seen_languages and not self.enchant.dict_exists(language):
            # Sometimes enchants *wants* a country code, other times it does not.
            # For the cases where it requires one, we look for the first language
            # code that enchant supports and use that one.
            for code in self._enchant_languages:
                if code.startswith(language+'_'):
                    self._seen_languages[language] = code
                    language = code
                    break
            else:
                # DictionaryDownloadWatcher (wired to LanguageController,
                # not this per-textview signal) handles trying to
                # download a missing dictionary - nothing to do here but
                # degrade gracefully for now.

                # We couldn't find a dictionary for "language", so we should make sure that we don't
                # have a spell checker for a different language on the text view. See bug 717.
                self._disable_checking(text_view)
                self._seen_languages[language] = None
                return

        language = self._seen_languages.get(language, language)
        if language is None:
            self._disable_checking(text_view)
            return

        # Activation runs on idle; only the latest language may run (#4441).
        text_view.spell_pending = language
        if getattr(text_view, 'spell_lang', None) == language:
            # No change necessary - already enabled
            return
        GLib.idle_add(self._activate_checker, text_view, language, priority=GLib.PRIORITY_LOW)

    def _activate_checker(self, text_view, language):
        # All the expensive stuff in here called on idle.
        if getattr(text_view, 'spell_pending', None) != language:
            # The language changed again before this ran.
            return
        try:
            spell = None
            try:
                spell = self.gtkspell.Checker.get_from_text_view(text_view)
            except SystemError as e:
                # At least on Mandriva .get_from_text_view() sometimes returns
                # a SystemError without a description. Things seem to work fine
                # anyway, so let's ignore it and hope for the best.
                logging.debug("gtkspell.Checker.get_from_text_view() raised: %s", e)
            if spell is None:
                spell = self.gtkspell.Checker()
                # Creating a checker binds gtkspell3 to its own catalogs.
                rebind_library_domain(b"gtkspell3")
                # Attaching checks the text, so it needs a language
                # first (#4439).
                spell.set_language(language)
                spell.attach(text_view)
            else:
                spell.set_language(language)
            spell.recheck_all()
            text_view.spell_lang = language
        except Exception as e:
            logging.exception("Could not initialize spell checking: %s", e)
            self.gtkspell = None
            #TODO: unload plugin

    def _on_apply_tag(self, buffer, tag, start, end, textbox):
        """Don't mark words in placeables (variables, tags) as misspelled."""
        if tag.props.name == 'gtkspell-misspelled' and _in_placeable(textbox, start, end):
            buffer.stop_emission_by_name('apply-tag')

    def _on_populate_popup(self, textbox, menu):
        editable = textbox.get_editable()
        _entries_above_separator = False
        for item in menu:
            if item.get_name() == 'GtkSeparatorMenuItem':
                if not _entries_above_separator:
                    menu.remove(item)
                break

            label = item.get_property('label')

            if not editable and not _is_dictionary_entry(label):
                menu.remove(item)
                continue

            # We don't want a language selector - we have our own
            if label == _gtkspell_text('Languages'):
                menu.remove(item)
                if not _entries_above_separator:
                    continue

            _entries_above_separator = True
