#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Fuzz failures already filed. The fuzz job fails on a failure that no
entry matches (a new bug), on an entry whose failure didn't happen
(fixed: remove the entry), and on an entry whose issue is closed.

Each entry: issue, sweep (one or a list), cases (corpus case names, or
ALL: at least one case of each sweep), kind, and match (text the
signature or detail must contain). platforms defaults to all three.
strict=False: allowed but not required, for timings close to the limit
and for what only the random part hits.
"""

from results import ALL
from sweep import SECTIONS

BLANK = ['empty', 'one space', 'spaces only', 'tab', 'newline only', 'NBSP only']
SOURCES = ['source', 'source-xliff', 'source-ts', 'source-tbx', 'source-tmx', 'plural-source']
# What configparser loses (#4346): surrounding whitespace and lines starting ; or #.
STRIPPED = ['leading/trailing space', 'trailing newline', '10k chars words', '2000 lines', 'ini syntax']
DIALOG_INI = ['addlang-name', 'addlang-plural', 'lookup-name', 'lookup-url', 'translator-name', 'translator-email',
              'translator-team']
EVERY_SWEEP = [sweep for sweeps in SECTIONS.values() for sweep in sweeps] + ['random']

KNOWN_BUGS = [
    dict(issue=4335, sweep=SOURCES, kind='timeout', match='',
         cases=['4096 chars one word']),
    # A long word typed into the target is parsed the same way.
    dict(issue=4335, sweep='random', kind='timeout', match='placeables', cases=ALL, strict=False),
    # Finding the word shows its unit; close to the slow limit on some runners.
    dict(issue=4335, sweep=['search', 'search-regex'], kind='slow', match='',
         cases=['4096 chars one word'], strict=False),
    # Fields whose dialog refuses a blank value.
    dict(issue=4346, sweep=['addlang-name', 'lookup-name', 'lookup-url'], kind='config-roundtrip', match='',
         cases=STRIPPED),
    dict(issue=4346, sweep=['addlang-plural', 'translator-name', 'translator-email', 'translator-team'],
         kind='config-roundtrip', match='', cases=STRIPPED + BLANK[1:]),
    # 5-15 s depending on the runner, so not required.
    dict(issue=4347, sweep=['target', 'target-xliff', 'search', 'search-regex', 'replace', 'replace-all', 'keys',
                            'glossary'] + SOURCES,
         kind='slow', match='', cases=['2000 lines'], strict=False),
    dict(issue=4348, sweep=SOURCES, kind='critical',
         match='pango_layout_get_cursor_pos', cases=['CRLF']),
    # A match between the CR and LF of a CRLF unit.
    dict(issue=4348, sweep=['search', 'search-regex'], kind='critical', match='pango_layout_get_cursor_pos',
         cases=['newline only']),
    dict(issue=4349, sweep=['source', 'plural-source'], kind='display-mismatch', match='',
         cases=['NUL']),
    dict(issue=4396, sweep=DIALOG_INI, kind='config-roundtrip', match='', cases=['CRLF', 'lone CR']),
    dict(issue=4397, sweep='addlang-name', kind='glib-warning', match='32767',
         cases=['4096 chars one word'], platforms=['linux']),
    # Depends on the window and pane sizes as well as the text.
    dict(issue=4397, sweep=['context', 'notes', 'addlang-name'], kind='glib-warning', match='32767',
         cases=['4096 chars one word', '10k chars words', '100k chars', '2000 lines'], platforms=['linux'],
         strict=False),
    dict(issue=4398, sweep=['random', 'target', 'target-xliff'], kind='critical', match='GTK_IS_WIDGET', cases=ALL,
         strict=False),
    dict(issue=4398, sweep=['random', 'target', 'target-xliff'], kind='critical', match='GDK_IS_WINDOW', cases=ALL,
         strict=False),
    dict(issue=4398, sweep=['random', 'target', 'target-xliff'], kind='critical', match="'handler_id > 0'",
         cases=ALL, strict=False),
    dict(issue=4398, sweep=['random', 'target', 'target-xliff'], kind='critical', match='updating_count > 0',
         cases=ALL, strict=False),
    dict(issue=4400, sweep=EVERY_SWEEP, kind='critical', match='gtk_box_gadget_distribute', cases=ALL, strict=False),
    # Malformed files (#4388).
    # Not filed in Virtaal: to report to translate-toolkit after 1.0.0.
    dict(upstream='translate-toolkit: XLIFF entity references', sweep='file-xlf', kind='exception',
         match='TypeError _layout_update_sources', cases=['internal entity', 'external entity', 'entity expansion']),
    dict(upstream='translate-toolkit: XLIFF entity references', sweep='file-xlf', kind='save-unreadable',
         match='XMLSyntaxError', cases=['external entity', 'entity expansion']),
    dict(issue=4410, sweep=EVERY_SWEEP, kind='critical', match='width >= -1', cases=ALL, strict=False),
    # Config start-ups (fuzz_config.py, #4360).
    dict(issue=4397, sweep='config-virtaal.ini', kind='glib-warning', platforms=['linux'], strict=False, match='Gdk: Native Windows wider or taller than 32767 pixels are not supported',
         cases=['language.sourcelang: long']),
    dict(issue=4432, sweep='config-virtaal.ini', kind='critical', match=": enchant_broker_dict_exists: assertion 'tag && strlen(tag)' failed",
         cases=['language.targetlang: blank', 'language.targetlang: space']),
    dict(issue=4433, sweep='config-virtaal.ini', kind='log-error', match='ModuleNotFoundError <module>',
         cases=['whole file: 5 MB', 'whole file: binary garbage', 'whole file: byte order mark', 'whole file: directory', 'whole file: duplicate key', 'whole file: duplicate section', 'whole file: empty file', 'whole file: invalid UTF-8', 'whole file: no section header', 'whole file: only comments']),
    dict(issue=4433, sweep='config-virtaal.ini', kind='log-error', match='root _get_plugin_class',
         cases=['whole file: 5 MB', 'whole file: binary garbage', 'whole file: byte order mark', 'whole file: directory', 'whole file: duplicate key', 'whole file: duplicate section', 'whole file: empty file', 'whole file: invalid UTF-8', 'whole file: no section header', 'whole file: only comments']),
    dict(issue=4433, sweep='config-virtaal.ini', kind='log-error', match='Exception _get_plugin_class',
         cases=['whole file: 5 MB', 'whole file: binary garbage', 'whole file: byte order mark', 'whole file: directory', 'whole file: duplicate key', 'whole file: duplicate section', 'whole file: empty file', 'whole file: invalid UTF-8', 'whole file: no section header', 'whole file: only comments']),
    # Translation services (services.py, #4389).
    # Editing paths and interface languages (editing.py, #4411).
    # Windows' GtkSpell finishes in time; on Linux too since the spelling
    # language is set before the checker is attached (18f3ffdf).
    dict(issue=4443, sweep='spelling', kind='timeout', match='', cases=['100k chars'], platforms=['macos']),
    dict(issue=4448, sweep='spelling', kind='glib-warning', match='iso-codes', cases=ALL, platforms=['macos']),
    # Windows' runner is slower still; the stall also outlasts the case into the next few.
    dict(issue=4347, sweep='keys', kind='timeout', match='', cases=['2000 lines'], platforms=['windows'],
         strict=False),
    dict(issue=4347, sweep='autocorrect', kind='slow', match='',
         cases=['2000 lines', 'printf', 'python named', 'percent alone', 'url-escape'], strict=False),
    dict(issue=4453, sweep='autocorrect', kind='autocorrect-mismatch', match='', cases=['printf'], strict=False),
    dict(issue=4452, sweep='random', kind='timeout', match='', cases=['search'], platforms=['windows'], strict=False),
    dict(issue=4443, sweep='spelling', kind='slow', match='', cases=['10k chars words', '2000 lines'], strict=False),
    dict(issue=4348, sweep='glossary', kind='critical', match='pango_layout_get_cursor_pos', cases=['CRLF']),
    dict(issue=4335, sweep='glossary', kind='slow', match='', cases=['4096 chars one word'], strict=False),
    # Preferences loads every plug-in's class to list it.
    dict(issue=4433, sweep=[s for s in EVERY_SWEEP if s.startswith('ui-')], kind='log-error', match='IPython',
         cases=['preferences'], platforms=['linux']),
    dict(issue=4433, sweep=[s for s in EVERY_SWEEP if s.startswith('ui-')], kind='log-error',
         match='_get_plugin_class', cases=['preferences'], platforms=['linux']),
]
