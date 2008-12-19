#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
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
Lokalize. Translation Memory can be imported from Poedit and Lokalize.
"""

import logging
from gtk import gdk
import os
from os import path
import bsddb
import struct
import StringIO
try:
    from pysqlite2 import dbapi2
except ImportError:
    from sqlite3 import dbapi2
try:
    import iniparse as ConfigParser
except ImportError, e:
    import ConfigParser

from virtaal.common import pan_app
from virtaal.controllers import BasePlugin

from translate.storage.pypo import extractpoline
from translate.lang import data


def _prepare_db_string(string):
    """Helper method needed by the Berkeley DB TM converters."""
    string = '"%s"' % string
    string = unicode(extractpoline(string), 'utf-8')
    return string

class Plugin(BasePlugin):
    name = 'Migration assistant'
    version = 0.1

    def __init__(self, main_controller):
        self.main_controller = main_controller
        self._init_plugin()

    def _init_plugin(self):
        if path.exists(pan_app.settings.filename):
            logging.debug('Migration plugin not executed due to existing configuration')
            return

        message = _('It seems you have not yet used Virtaal.\n\nShould Virtaal try to import settings and data from other applications?')
        must_migrate = self.main_controller.show_prompt(_('Import data from other applications?'), message)
        if not must_migrate:
            logging.debug('Migration not done due to user choice')
            return

        # We'll store the tm here:
        self.tm = []
        # We actually need source, target, context, targetlanguage
        self.migrated = []

        #TODO: confirm Windows home for Poedit
        self.poedit_dir = path.expanduser('~/.poedit')

        #TODO: check if we can do better than hardcoding the kbabel location
        #this path is specified in ~/.kde/config/kbabel.defaultproject and kbabeldictrc
        self.kbabel_dir = path.expanduser('~/.kde/share/apps/kbabeldict/dbsearchengine')

        self.lokalize_rc = path.expanduser('~/.kde/share/config/lokalizerc')
        self.lokalize_tm_dir = path.expanduser('~/.kde/share/apps/lokalize/')

        self.poedit_settings_import()
        self.poedit_tm_import()
        self.kbabel_tm_import()
        self.lokalize_settings_import()
        self.lokalize_tm_import()

        if self.migrated:
            message = _('Migration was successfully completed') + '\n\n'
            message += _('The following items were migrated:') + '\n\n'
            message += u"\n".join([u" • %s" % item for item in self.migrated])
            self.main_controller.show_info(_('Migration completed'), message)
        else:
            message = _("Virtaal was not able to migrate any settings or data")
            self.main_controller.show_info(_('Nothing migrated'), message)
        logging.debug('Migration plugin executed')

    def poedit_settings_import(self):
        """Attempt to import the settings from Poedit."""
        config_filename = path.join(self.poedit_dir, 'config')
        if not path.exists(config_filename):
            return

        self.poedit_config = ConfigParser.ConfigParser()
        poedit_config_file = open(config_filename, 'r')
        contents = StringIO.StringIO('[poedit_headerless_file]\n' + poedit_config_file.read())
        poedit_config_file.close()
        self.poedit_config.readfp(contents)
        poedit_general = dict(self.poedit_config.items('poedit_headerless_file'))

        pan_app.settings.general['lastdir'] = poedit_general['last_file_path']
        pan_app.settings.translator['name'] = poedit_general['translator_name']
        pan_app.settings.translator['email'] = poedit_general['translator_email']
        pan_app.settings.write()
        poedit_tm_dict = dict(self.poedit_config.items('TM'))
        self.poedit_database_path = poedit_tm_dict['database_path']
        self.poedit_languages = poedit_tm_dict['languages'].split(':')
        self.migrated.append(_("Poedit settings"))

    def poedit_tm_import(self):
        """Attempt to import the Translation Memory used in KBabel."""
        if not hasattr(self, "poedit_config"):
            return
        # We need to work out wich language code to import, or do all, but
        # separately. For now, we look for the contentlang in the poedit
        #language list from the TM section of the config.
        lang = pan_app.settings.language["contentlang"]
        while lang:
            if lang in self.poedit_languages:
                break
            else:
                lang = data.simplercode(lang)
        else:
            return

        sources = bsddb.hashopen(path.join(self.poedit_database_path, lang, 'strings.db'), 'r')
        targets = bsddb.rnopen(path.join(self.poedit_database_path, lang, 'translations.db'), 'r')

        for source, str_index in sources.iteritems():
            # the index is a four byte integer encoded as a string
            # was little endian on my machine, not sure if it is universal
            index = struct.unpack('i', str_index)
            target = targets[index[0]][:-1] # null-terminated
            source = _prepare_db_string(source)
            target = _prepare_db_string(target)
            self.tm.append((source, target))

        logging.debug('%d units migrated from Poedit TM: %s.' % (len(sources), lang))
        sources.close()
        targets.close()
        self.migrated.append(_("Poedit's Translation Memory: %(database_language_code)s") % {"database_language_code": lang})

    def kbabel_tm_import(self):
        """Attempt to import the Translation Memory used in KBabel."""
        tm_filename = path.join(self.kbabel_dir, 'translations.af.db')
        if not path.exists(tm_filename):
            return
        translations = bsddb.btopen(tm_filename, 'r')

        for source, target in translations.iteritems():
            source = source[:-1] # null-terminated
            target = target[16:-1] # 16 bytes of padding, null-terminated
            source = _prepare_db_string(source)
            target = _prepare_db_string(target)
            self.tm.append((source, target))

        logging.debug('%d units migrated from KBabel TM.' % len(translations))
        translations.close()
        self.migrated.append(_("KBabel's Translation Memory"))

    def lokalize_settings_import(self):
        """Attempt to import the settings from Lokalize."""
        if not path.exists(self.lokalize_rc):
            return

        lokalize_config = ConfigParser.ConfigParser()
        lokalize_config.read(self.lokalize_rc)
        lokalize_identity = dict(lokalize_config.items('Identity'))

        pan_app.settings.translator['name'] = lokalize_identity['authorlocalizedname']
        pan_app.settings.translator['email'] = lokalize_identity['authoremail']
        pan_app.settings.translator['team'] = lokalize_identity['defaultmailinglist']
        pan_app.settings.general['lastdir'] = path.dirname(dict(lokalize_config.items('State'))['project'])

        pan_app.settings.write()
        self.migrated.append(_("Lokalize settings"))

    def lokalize_tm_import(self):
        """Attempt to import the Translation Memory used in Lokalize."""
        if not path.isdir(self.lokalize_tm_dir):
            return
        databases = [name for name in os.listdir(self.lokalize_tm_dir) if path.exists(name)]
        for database in databases:
            self.do_lokalize_tm_import(database)

    def do_lokalize_tm_import(self, filename):
        """Import the given Translation Memory file used by Lokalize."""
        connection = dbapi2.connect(filename)
        cursor = connection.cursor()
        cursor.execute("""SELECT english, target from tm_main;""")
        self.tm.extend(cursor.fetchall())
        connection.close()
        self.migrated.append(_("Lokalize's Translation Memory: %(database_name)s") % {"database_name": path.basename(filename)})

