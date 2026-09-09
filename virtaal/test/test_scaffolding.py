#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os
import tempfile

from translate.storage import factory

from virtaal.controllers.checkscontroller import ChecksController
from virtaal.controllers.langcontroller import LanguageController
from virtaal.controllers.maincontroller import MainController
from virtaal.controllers.modecontroller import ModeController
from virtaal.controllers.storecontroller import StoreController
from virtaal.controllers.undocontroller import UndoController
from virtaal.controllers.unitcontroller import UnitController


class TestScaffolding:
    def setup_class(self):
        self.main_controller = MainController()
        self.store_controller = StoreController(self.main_controller)
        self.unit_controller = UnitController(self.store_controller)
        self.checks_controller = ChecksController(self.main_controller)

        # Load additional built-in modules
        self.undo_controller = UndoController(self.main_controller)
        self.mode_controller = ModeController(self.main_controller)
        self.lang_controller = LanguageController(self.main_controller)

        po_contents = """# Afrikaans (af) localisation of Virtaal.
# Copyright (C) 2008 Zuza Software Foundation (Translate.org.za)
# This file is distributed under the same license as the Virtaal package.
# Dwayne Bailey <dwayne@translate.org.za>, 2008
# F Wolff <friedel@translate.org.za>, 2008
msgid ""
msgstr ""
"Project-Id-Version: Virtaal 0.1\\n"
"Report-Msgid-Bugs-To: translate-devel@lists.sourceforge.net\\n"
"POT-Creation-Date: 2008-10-14 15:33+0200\\n"
"PO-Revision-Date: 2008-10-14 15:46+0200\\n"
"Last-Translator: F Wolff <friedel@translate.org.za>\\n"
"Language-Team: translate-discuss-af@lists.sourceforge.net\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"
"X-Generator: Virtaal 0.2\\n"

#: ../bin/virtaal:41
msgid "You must specify a directory or a translation file for --terminology"
msgstr "U moet 'n gids of vertaallêer spesifiseer vir --terminology"

#: ../bin/virtaal:46
#, c-format
msgid "%prog [options] [translation_file]"
msgstr "%prog [opsies] [vertaallêer]"

#, fuzzy
#: ../bin/virtaal:49
msgid "PROFILE"
msgstr "PROFIEL"
"""
        self.testfile = tempfile.mkstemp(suffix='.po', prefix='test_storemodel')
        os.write(self.testfile[0], po_contents.encode('UTF-8'))
        os.close(self.testfile[0])
        self.trans_store = factory.getobject(self.testfile[1])

    def teardown_class(self):
        os.unlink(self.testfile[1])
