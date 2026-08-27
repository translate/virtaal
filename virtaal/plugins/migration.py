#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2009 Zuza Software Foundation
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

"""Plugin to import data from other applications.

Currently there is some support for importing settings from Poedit and
Lokalize, and Translation Memory from Lokalize. (Poedit's and KBabel's TM
import both relied on the Python 2-only bsddb module and were removed.)
"""

import logging
import os
import sys
from os import path

from io import StringIO
import configparser as ConfigParser

try:
    from sqlite3 import dbapi2
except ImportError:
    from pysqlite2 import dbapi2

from virtaal.common import pan_app
from virtaal.controllers.baseplugin import BasePlugin

from virtaal.support import tmdb


class Plugin(BasePlugin):
    description = _('Migrate settings from KBabel, Lokalize and/or Poedit to Virtaal.')
    display_name = _('Migration Assistant')
    version = 0.1

    default_config = {
        "tmdb": path.join(pan_app.get_config_dir(), "tm.db")
    }

    def __init__(self, internal_name, main_controller):
        self.internal_name = internal_name
        self.main_controller = main_controller
        self.load_config()
        self._init_plugin()

    def _init_plugin(self):
        # Set up the source paths before deciding anything - both the
        # up-front "is there real evidence" check below and the actual
        # import methods need these, and previously the paths (and the
        # existence checks that use them) were only ever computed
        # *after* the user had already said yes to a completely
        # unconditional prompt.
        if sys.platform == "darwin":
            self.poedit_dir = path.expanduser('~/Library/Preferences')
        else:
            self.poedit_dir = path.expanduser('~/.poedit')

        # KDE moved app configs/data from ~/.kde/share/{config,apps}/ to
        # the XDG base dirs with the KDE4->Frameworks 5 transition
        # (~2014) - these are the current locations, not the ~/.kde/...
        # ones this code originally targeted.
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME') or path.expanduser('~/.config')
        xdg_data_home = os.environ.get('XDG_DATA_HOME') or path.expanduser('~/.local/share')
        self.lokalize_rc = path.join(xdg_config_home, 'lokalizerc')
        self.lokalize_tm_dir = path.join(xdg_data_home, 'lokalize')

        # pan_app.settings.plugin_state[...] = "disabled" further down
        # is only ever set in memory unless persisted here - without an
        # explicit write(), every launch re-reads a config file that was
        # never actually updated, so declining once never sticks.
        #
        # Also gated on real evidence before ever prompting at all: no
        # Poedit/Lokalize config or TM data found means no prompt, not
        # "prompt then find nothing" - see _has_anything_to_migrate().
        if not self._has_anything_to_migrate():
            logging.debug('Migration: nothing found to import - staying silent')
            pan_app.settings.plugin_state[self.internal_name] = "disabled"
            pan_app.settings.write()
            return

        message = _('Should Virtaal try to import settings and data from other applications?')
        must_migrate = self.main_controller.show_prompt(_('Import data from other applications?'), message)
        if not must_migrate:
            logging.debug('Migration not done due to user choice')
        else:
            # We'll store the tm here:
            self.tmdb = tmdb.TMDB(self.config["tmdb"])
            # We actually need source, target, context, targetlanguage
            self.migrated = []

            self.poedit_settings_import()
            self.lokalize_settings_import()
            self.lokalize_tm_import()

            if self.migrated:
                message = _('Migration was successfully completed') + '\n\n'
                message += _('The following items were migrated:') + '\n\n'
                message += u"\n".join([u" • %s" % item for item in self.migrated])
                #   (we can mark this ^^^ for translation if somebody asks)
                self.main_controller.show_info(_('Migration completed'), message)
            else:
                message = _("Virtaal was not able to migrate any settings or data")
                self.main_controller.show_info(_('Nothing migrated'), message)
            logging.debug('Migration plugin executed')

        pan_app.settings.plugin_state[self.internal_name] = "disabled"
        pan_app.settings.write()

    def _has_anything_to_migrate(self):
        """Cheap existence-only checks (no parsing) for whether *any*
            supported source has real data to offer - the gate for
            whether to prompt at all."""
        if self._poedit_config_exists():
            return True
        if path.exists(self.lokalize_rc):
            return True
        if path.isdir(self.lokalize_tm_dir):
            if any(name.endswith('.db') and not name.endswith('-journal.db')
                   for name in os.listdir(self.lokalize_tm_dir)):
                return True
        return False

    def _poedit_config_exists(self):
        if sys.platform == 'darwin':
            config_filename = path.join(self.poedit_dir, 'net.poedit.Poedit.cfg')
        else:
            config_filename = path.join(self.poedit_dir, 'config')
        if path.exists(config_filename):
            return True
        if sys.platform != 'win32':
            return False
        try:
            import winreg
        except ImportError:
            return False
        try:
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Vaclav Slavik\Poedit")
            return True
        except OSError:
            return False

    def poedit_settings_import(self):
        """Attempt to import the settings from Poedit."""
        if sys.platform == 'darwin':
            config_filename = path.join(self.poedit_dir, 'net.poedit.Poedit.cfg')
        else:
            config_filename = path.join(self.poedit_dir, 'config')
        get_thing = None
        if not path.exists(config_filename):
            # winreg (no underscore) is the Python 3 name; the Python 2
            # name was _winreg.
            try:
                import winreg
            except Exception as e:
                return

            def get_thing(section, item):
                key = None
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Vaclav Slavik\Poedit\%s" % section)
                except WindowsError:
                    return

                data = None
                try:
                    # This is very inefficient, but who cares?
                    for i in range(100):
                        name, data, type = winreg.EnumValue(key, i)
                        if name == item:
                            break
                except EnvironmentError as e:
                    pass
                except Exception as e:
                    logging.exception("Error obtaining from registry: %s, %s", section, item)
                return data

        else:
            self.poedit_config = ConfigParser.ConfigParser()
            poedit_config_file = open(config_filename, 'r')
            contents = StringIO('[poedit_headerless_file]\n' + poedit_config_file.read())
            poedit_config_file.close()
            self.poedit_config.read_file(contents)
            def get_thing(section, item):
                dictionary = dict(self.poedit_config.items(section or 'poedit_headerless_file'))
                return dictionary.get(item, None)

        if get_thing is None:
            return

        lastdir = get_thing('', 'last_file_path')
        name = get_thing('', 'translator_name')
        translator_email = get_thing('', 'translator_email')

        if lastdir:
            pan_app.settings.general['lastdir'] = lastdir
        if name:
            pan_app.settings.translator['name'] = name
        if translator_email:
            pan_app.settings.translator['email'] = translator_email

        if lastdir or name or translator_email:
            pan_app.settings.write()
            self.migrated.append(_("Poedit settings"))

    # poedit_tm_import() and kbabel_tm_import() used to live here: both
    # imported Poedit's/KBabel's Translation Memory out of Berkeley DB
    # files via the stdlib `bsddb` module. `bsddb` was Python 2-only and
    # was never ported to Python 3 (no replacement in the standard
    # library), so both were permanently unreachable dead code under
    # Python 3 - the try/except above always left bsddb as None, and both
    # methods bailed out in their very first line whenever that was the
    # case. Removed rather than ported, along with the now-unused
    # `_prepare_db_string()` helper (translate.storage.pypo.extractpoline,
    # which it needed, was itself removed upstream - not worth chasing
    # for code nothing could ever call).

    def lokalize_settings_import(self):
        """Attempt to import the settings from Lokalize."""
        if not path.exists(self.lokalize_rc):
            return

        lokalize_config = ConfigParser.ConfigParser()
        lokalize_config.read(self.lokalize_rc)
        lokalize_identity = dict(lokalize_config.items('Identity'))

        pan_app.settings.translator['name'] = lokalize_identity['authorname']
        pan_app.settings.translator['email'] = lokalize_identity['authoremail']
        pan_app.settings.translator['team'] = lokalize_identity['defaultmailinglist']
        pan_app.settings.general['lastdir'] = path.dirname(dict(lokalize_config.items('State'))['project'])

        pan_app.settings.write()
        self.migrated.append(_("Lokalize settings"))

    def lokalize_tm_import(self):
        """Attempt to import the Translation Memory used in Lokalize."""
        if not path.isdir(self.lokalize_tm_dir):
            return
        # Each configured TM in Lokalize is a "<name>.db" sqlite file
        # directly under this directory (see src/tm/dbfilesmodel.cpp and
        # the TM_DATABASE_EXTENSION/REMOTETM_DATABASE_EXTENSION macros in
        # src/tm/jobs.h upstream) - "*-journal.db" is sqlite's own journal
        # file, not a database, and "*.remotedb" just points at a remote
        # TM server, with nothing local to read.
        for name in os.listdir(self.lokalize_tm_dir):
            if not name.endswith('.db') or name.endswith('-journal.db'):
                continue
            filename = path.join(self.lokalize_tm_dir, name)
            if path.isfile(filename):
                self.do_lokalize_tm_import(filename)

    def do_lokalize_tm_import(self, filename):
        """Import the given Translation Memory file used by Lokalize."""
        connection = dbapi2.connect(filename)
        cursor = connection.cursor()
        try:
            # tm_config holds one row per (key, value): key 2 is the
            # source language code, key 3 the target - see setConfig()/
            # getConfig() in src/tm/jobs.cpp upstream. Older/emptied
            # databases may not have it, hence the fallback below.
            cursor.execute("SELECT value FROM tm_config WHERE key = 2;")
            row = cursor.fetchone()
            source_lang = row[0] if row else "en"
            cursor.execute("SELECT value FROM tm_config WHERE key = 3;")
            row = cursor.fetchone()
            target_lang = row[0] if row else self.main_controller.lang_controller.target_lang.code

            # Lokalize normalizes its schema across source_strings/
            # target_strings/main (foreign keys), not a single flat table -
            # see initSqliteDb() in src/tm/jobs.cpp upstream.
            cursor.execute("""
                SELECT source_strings.source, target_strings.target
                FROM main
                JOIN source_strings ON main.source = source_strings.id
                JOIN target_strings ON main.target = target_strings.id;
            """)
            count = 0
            for (source, target) in cursor:
                unit = { "source" : source,
                         "target" : target,
                         "context" : ""
                         }
                self.tmdb.add_dict(unit, source_lang, target_lang, commit=False)
                count += 1
        finally:
            connection.close()

        if count:
            self.tmdb.connection.commit()
            self.migrated.append(_("Lokalize's Translation Memory: %(database_name)s") % \
                    {"database_name": path.basename(filename)})
