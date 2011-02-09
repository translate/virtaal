#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2011 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import logging
from gobject import SIGNAL_RUN_FIRST, timeout_add

from virtaal.common import GObjectWrapper

from basecontroller import BaseController

check_names = {
    'fuzzy': _(u"Fuzzy"),
    'untranslated': _(u"Untranslated"),
    'accelerators': _(u"Accelerators"),
    'acronyms': _(u"Acronyms"),
    'blank': _(u"Blank"),
    'brackets': _(u"Brackets"),
    'compendiumconflicts': _(u"Compendium conflict"),
    'credits': _(u"Translator credits"),
    'doublequoting': _(u"Double quotes"),
    'doublespacing': _(u"Double spaces"),
    'doublewords': _(u"Repeated word"),
    'emails': _(u"E-mail"),
    'endpunc': _(u"Ending punctuation"),
    'endwhitespace': _(u"Ending whitespace"),
    'escapes': _(u"Escapes"),
    'filepaths': _(u"File paths"),
    'functions': _(u"Functions"),
    'gconf': _(u"GConf values"),
    'kdecomments': _(u"Old KDE comment"),
    'long': _(u"Long"),
    'musttranslatewords': _(u"Must translate words"),
    'newlines': _(u"Newlines"),
    'nplurals': _(u"Number of plurals"),
    'notranslatewords': _(u"Don't translate words"),
    'numbers': _(u"Numbers"),
    'options': _(u"Options"),
    'printf': _(u"printf()"),
    'puncspacing': _(u"Punctuation spacing"),
    'purepunc': _(u"Pure punctuation"),
    'sentencecount': _(u"Number of sentences"),
    'short': _(u"Short"),
    'simplecaps': _(u"Simple capitalization"),
    'simpleplurals': _(u"Simple plural(s)"),
    'singlequoting': _(u"Single quotes"),
    'spellcheck': _(u"Spelling"),
    'startcaps': _(u"Starting capitalization"),
    'startpunc': _(u"Starting punctuation"),
    'startwhitespace': _(u"Starting whitespace"),
    'tabs': _(u"Tabs"),
    'unchanged': _(u"Unchanged"),
    'urls': _(u"URLs"),
    'validchars': _(u"Valid characters"),
    'variables': _(u"Placeholders"),
    'xmltags': _(u"XML tags"),

# Consider:
#  -  hassuggestion
#  -  isreview
}


class ChecksController(BaseController):
    """Controller for quality checks."""

    __gtype_name__ = 'ChecksController'
    __gsignals__ = {
        'checker-set':  (SIGNAL_RUN_FIRST, None, (object,)),
        'unit-checked': (SIGNAL_RUN_FIRST, None, (object, object, object))
    }

    CHECK_TIMEOUT = 500
    """Time to wait before performing checks on the current unit."""

    # INITIALIZERS #
    def __init__(self, main_controller):
        GObjectWrapper.__init__(self)

        self.main_controller = main_controller
        self.main_controller.checks_controller = self
        self.store_controller = main_controller.store_controller

        main_controller.store_controller.connect('store-loaded', self._on_store_loaded)
        main_controller.unit_controller.connect('unit-modified', self._on_unit_modified)
        if main_controller.lang_controller:
            main_controller.lang_controller.connect('target-lang-changed', self._on_target_lang_changed)
        else:
            main_controller.connect('controller-registered', self._on_controller_registered)

        self.code = None
        self._checker = None
        self._check_timer_active = False
        self._checker_code_to_name = {
              "default": _('Default'),
              "openoffice":  _('OpenOffice.org'),
              "mozilla": _('Mozilla'),
              "kde": _('KDE'),
              "gnome": _('GNOME'),
              "drupal": _('Drupal'),
        }
        self._checker_name_to_code = dict([(value, key) for (key, value) in self._checker_code_to_name.items()])
        self._checker_info = None
        self._checker_menu_items = {}
        self._cursor_connection = ()
        self.last_unit = None

        self._projview = None
        self._unitview = None

        if self.store_controller.get_store():
            # We are too late for the initial 'store-loaded'
            self._on_store_loaded(self.store_controller)

    # ACCESSORS #
    def _get_checker_info(self):
        if not self._checker_info:
            from translate.filters import checks
            self._checker_info = {
                # XXX: Add other checkers below with a localisable string as key
                #      (used on the GUI) and a checker class as the value.
                'default':    checks.StandardChecker,
                'openoffice': checks.OpenOfficeChecker,
                'mozilla':    checks.MozillaChecker,
                'drupal':     checks.DrupalChecker,
                'gnome':      checks.GnomeChecker,
                'kde':        checks.KdeChecker,
            }
        return self._checker_info
    checker_info = property(_get_checker_info)

    def _get_projview(self):
        from virtaal.views.checksprojview import ChecksProjectView
        if self._projview is None:
            self._projview = ChecksProjectView(self)
            self._projview.show()
        return self._projview
    projview = property(_get_projview)

    def _get_unitview(self):
        from virtaal.views.checksunitview import ChecksUnitView
        if self._unitview is None:
            self._unitview = ChecksUnitView(self)
            self._unitview.show()
        return self._unitview
    unitview = property(_get_unitview)

    def get_checker(self):
        return self._checker

    def set_checker_by_name(self, name):
        self.set_checker_by_code(self._checker_name_to_code.get(name, None))

    def set_checker_by_code(self, code):
        if code is None:
            code = "default"
        target_lang = self.main_controller.lang_controller.target_lang.code
        if not target_lang:
            target_lang = None
        self._checker = self.checker_info.get(code, self.checker_info["default"])()
        self._checker.config.updatetargetlanguage(target_lang)

        self.emit('checker-set', self.get_checker())
        self.projview.set_checker_name(self._checker_code_to_name[code])
        self.code = code
        if self.main_controller.unit_controller.current_unit:
            self.check_unit(self.main_controller.unit_controller.current_unit)


    # METHODS #
    def check_unit(self, unit):
        checker = self.get_checker()
        if not checker:
            logging.debug('No checker instantiated :(')
            return
        self.last_failures = checker.run_filters(unit)
        if self.last_failures:
            logging.debug('Failures: %s' % (self.last_failures))
        self.unitview.update(self.last_failures)
        self.emit('unit-checked', unit, checker, self.last_failures)
        return self.last_failures

    def _check_timer_expired(self, unit):
        self._check_timer_active = False
        if unit is not self.last_unit:
            return
        self.check_unit(unit)

    def _start_check_timer(self):
        if self._check_timer_active:
            return
        if not self.last_unit:
            # haven't changed units yet, probably strange timing issue
            return
        self._check_timer_active = True
        timeout_add(self.CHECK_TIMEOUT, self._check_timer_expired, self.last_unit)

    def get_check_name(self, check):
        """Return the human readable form of the given check name."""
        name = check_names.get(check, None)
        if not name and check.startswith('check-'):
            check = check[len('check-'):]
            name = check_names.get(check, None)
        if not name:
            name = check
        return name


    # EVENT HANDLERS #
    def _on_controller_registered(self, main_controller, controller):
        if controller is main_controller.lang_controller:
            controller.connect('target-lang-changed', self._on_target_lang_changed)

    def _on_cursor_changed(self, cursor):
        self.last_unit = cursor.deref()
        self.check_unit(self.last_unit)

    def _on_target_lang_changed(self, lang_controller, langcode):
        current_checker = self.get_checker()
        if current_checker:
           current_checker.config.updatetargetlanguage(langcode)
           self.emit('checker-set', current_checker)
           if self.last_unit:
               self.check_unit(self.last_unit)

    def _on_store_loaded(self, store_controller):
        self.set_checker_by_code(store_controller.store._trans_store.getprojectstyle())
        if self._cursor_connection:
            widget, connect_id = self._cursor_connection
            widget.disconnect(connect_id)
        self._cursor_connection = (
            store_controller.cursor,
            store_controller.cursor.connect('cursor-changed', self._on_cursor_changed)
        )
        self._on_cursor_changed(store_controller.cursor)

    def _on_unit_modified(self, unit_controller, unit):
        self._start_check_timer()
