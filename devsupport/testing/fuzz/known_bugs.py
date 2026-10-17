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
MARKUP = ['xml tags', 'xml unbalanced', 'entities', 'url', 'shell', 'accelerators', 'email-ish']
DIALOG_INI = ['addlang-name', 'addlang-plural', 'lookup-name', 'lookup-url', 'translator-name', 'translator-email',
              'translator-team']
EVERY_SWEEP = [sweep for sweeps in SECTIONS.values() for sweep in sweeps] + ['random']

KNOWN_BUGS = [
    dict(issue=4331, sweep='addlang-code', kind='exception', match='ValueError _load_recent',
         cases=['pipes and commas', 'regex meta']),
    dict(issue=4335, sweep=SOURCES, kind='timeout', match='',
         cases=['4096 chars one word']),
    # Finding the word shows its unit; close to the slow limit on some runners.
    dict(issue=4335, sweep=['search', 'search-regex'], kind='slow', match='',
         cases=['4096 chars one word'], strict=False),
    dict(issue=4342, sweep='addterm-existing', kind='display-mismatch', match='existing translations',
         cases=MARKUP + ['pango markup']),
    # GTK on macOS doesn't log this warning.
    dict(issue=4342, sweep='addterm-existing', kind='glib-warning', match='Failed to set text', cases=MARKUP,
         platforms=['linux', 'windows']),
    # Fields whose dialog refuses a blank value.
    dict(issue=4346, sweep=['addlang-name', 'lookup-name', 'lookup-url'], kind='config-roundtrip', match='',
         cases=STRIPPED),
    dict(issue=4346, sweep=['addlang-plural', 'translator-name', 'translator-email', 'translator-team'],
         kind='config-roundtrip', match='', cases=STRIPPED + BLANK[1:]),
    # 5-15 s depending on the runner, so not required.
    dict(issue=4347, sweep=['target', 'target-xliff', 'search', 'search-regex', 'replace', 'replace-all'] + SOURCES,
         kind='slow', match='', cases=['2000 lines'], strict=False),
    dict(issue=4348, sweep=SOURCES, kind='critical',
         match='pango_layout_get_cursor_pos', cases=['CRLF']),
    # A match between the CR and LF of a CRLF unit.
    dict(issue=4348, sweep=['search', 'search-regex'], kind='critical', match='pango_layout_get_cursor_pos',
         cases=['newline only']),
    dict(issue=4349, sweep=['source', 'plural-source'], kind='display-mismatch', match='',
         cases=['NUL']),
    dict(issue=4351, sweep='addlang-plural', kind='file-invalid', match='Plural-Forms',
         cases=ALL),
    dict(issue=4396, sweep=DIALOG_INI, kind='config-roundtrip', match='', cases=['CRLF', 'lone CR']),
    dict(issue=4397, sweep=['context', 'notes', 'addlang-name'], kind='glib-warning', match='32767',
         cases=['4096 chars one word'], platforms=['linux']),
    dict(issue=4397, sweep=['context', 'notes', 'addlang-name'], kind='glib-warning', match='32767',
         cases=['10k chars words', '100k chars', '2000 lines'], platforms=['linux'], strict=False),
    dict(issue=4398, sweep='random', kind='critical', match='GTK_IS_WIDGET', cases=ALL, strict=False),
    dict(issue=4398, sweep='random', kind='critical', match='GDK_IS_WINDOW', cases=ALL, strict=False),
    dict(issue=4398, sweep=['random', 'target', 'target-xliff'], kind='critical', match="'handler_id > 0'",
         cases=ALL, strict=False),
    dict(issue=4398, sweep=['random', 'target', 'target-xliff'], kind='critical', match='updating_count > 0',
         cases=ALL, strict=False),
    dict(issue=4400, sweep=EVERY_SWEEP, kind='critical', match='gtk_box_gadget_distribute', cases=ALL, strict=False),
]
