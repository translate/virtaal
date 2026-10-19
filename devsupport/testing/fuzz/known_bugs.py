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
    dict(issue=4351, sweep='addlang-plural', kind='file-invalid', match='Plural-Forms',
         cases=ALL),
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
    dict(issue=4340, sweep='config-langs.ini', kind='config-reset', match='',
         cases=['whole file: byte order mark']),
    dict(issue=4340, sweep='config-plugins.ini', kind='log-error', match='ValueError _init_plugin',
         cases=['terminology.max_matches: None', 'terminology.max_matches: RTL', 'terminology.max_matches: blank', 'terminology.max_matches: bool', 'terminology.max_matches: brackets', 'terminology.max_matches: comma', 'terminology.max_matches: control', 'terminology.max_matches: exponent', 'terminology.max_matches: float', 'terminology.max_matches: long', 'terminology.max_matches: newline', 'terminology.max_matches: non-ASCII', 'terminology.max_matches: one code', 'terminology.max_matches: pair junk', 'terminology.max_matches: percent', 'terminology.max_matches: percent format', 'terminology.max_matches: pipe', 'terminology.max_matches: relative path', 'terminology.max_matches: space', 'terminology.max_matches: word', 'terminology.min_quality: None', 'terminology.min_quality: RTL', 'terminology.min_quality: blank', 'terminology.min_quality: bool', 'terminology.min_quality: brackets', 'terminology.min_quality: comma', 'terminology.min_quality: control', 'terminology.min_quality: exponent', 'terminology.min_quality: float', 'terminology.min_quality: long', 'terminology.min_quality: newline', 'terminology.min_quality: non-ASCII', 'terminology.min_quality: one code', 'terminology.min_quality: pair junk', 'terminology.min_quality: percent', 'terminology.min_quality: percent format', 'terminology.min_quality: pipe', 'terminology.min_quality: relative path', 'terminology.min_quality: space', 'terminology.min_quality: word', 'tm.max_matches: None', 'tm.max_matches: RTL', 'tm.max_matches: blank', 'tm.max_matches: bool', 'tm.max_matches: brackets', 'tm.max_matches: comma', 'tm.max_matches: control', 'tm.max_matches: exponent', 'tm.max_matches: float', 'tm.max_matches: long', 'tm.max_matches: newline', 'tm.max_matches: non-ASCII', 'tm.max_matches: one code', 'tm.max_matches: pair junk', 'tm.max_matches: percent', 'tm.max_matches: percent format', 'tm.max_matches: pipe', 'tm.max_matches: relative path', 'tm.max_matches: space', 'tm.max_matches: word', 'tm.min_quality: None', 'tm.min_quality: RTL', 'tm.min_quality: blank', 'tm.min_quality: bool', 'tm.min_quality: brackets', 'tm.min_quality: comma', 'tm.min_quality: control', 'tm.min_quality: exponent', 'tm.min_quality: float', 'tm.min_quality: long', 'tm.min_quality: newline', 'tm.min_quality: non-ASCII', 'tm.min_quality: one code', 'tm.min_quality: pair junk', 'tm.min_quality: percent', 'tm.min_quality: percent format', 'tm.min_quality: pipe', 'tm.min_quality: relative path', 'tm.min_quality: space', 'tm.min_quality: word']),
    dict(issue=4340, sweep='config-plugins.ini', kind='log-error', match='ValueError __init__',
         cases=['lookup.backends_dialog_width: None', 'lookup.backends_dialog_width: RTL', 'lookup.backends_dialog_width: blank', 'lookup.backends_dialog_width: bool', 'lookup.backends_dialog_width: brackets', 'lookup.backends_dialog_width: comma', 'lookup.backends_dialog_width: control', 'lookup.backends_dialog_width: exponent', 'lookup.backends_dialog_width: float', 'lookup.backends_dialog_width: long', 'lookup.backends_dialog_width: newline', 'lookup.backends_dialog_width: non-ASCII', 'lookup.backends_dialog_width: one code', 'lookup.backends_dialog_width: pair junk', 'lookup.backends_dialog_width: percent', 'lookup.backends_dialog_width: percent format', 'lookup.backends_dialog_width: pipe', 'lookup.backends_dialog_width: relative path', 'lookup.backends_dialog_width: space', 'lookup.backends_dialog_width: word']),
    dict(issue=4340, sweep='config-plugins.ini', kind='exception', match='KeyError ',
         cases=['lookup.backends_dialog_width: None', 'lookup.backends_dialog_width: RTL', 'lookup.backends_dialog_width: blank', 'lookup.backends_dialog_width: bool', 'lookup.backends_dialog_width: brackets', 'lookup.backends_dialog_width: comma', 'lookup.backends_dialog_width: control', 'lookup.backends_dialog_width: exponent', 'lookup.backends_dialog_width: float', 'lookup.backends_dialog_width: long', 'lookup.backends_dialog_width: newline', 'lookup.backends_dialog_width: non-ASCII', 'lookup.backends_dialog_width: one code', 'lookup.backends_dialog_width: pair junk', 'lookup.backends_dialog_width: percent', 'lookup.backends_dialog_width: percent format', 'lookup.backends_dialog_width: pipe', 'lookup.backends_dialog_width: relative path', 'lookup.backends_dialog_width: space', 'lookup.backends_dialog_width: word']),
    dict(issue=4340, sweep='config-plugins.ini', kind='incomplete', match='look-up',
         cases=['lookup.backends_dialog_width: None', 'lookup.backends_dialog_width: RTL', 'lookup.backends_dialog_width: blank', 'lookup.backends_dialog_width: bool', 'lookup.backends_dialog_width: brackets', 'lookup.backends_dialog_width: comma', 'lookup.backends_dialog_width: control', 'lookup.backends_dialog_width: exponent', 'lookup.backends_dialog_width: float', 'lookup.backends_dialog_width: long', 'lookup.backends_dialog_width: newline', 'lookup.backends_dialog_width: non-ASCII', 'lookup.backends_dialog_width: one code', 'lookup.backends_dialog_width: pair junk', 'lookup.backends_dialog_width: percent', 'lookup.backends_dialog_width: percent format', 'lookup.backends_dialog_width: pipe', 'lookup.backends_dialog_width: relative path', 'lookup.backends_dialog_width: space', 'lookup.backends_dialog_width: word']),
    dict(issue=4340, sweep='config-plugins.ini', kind='config-reset', match='',
         cases=['whole file: byte order mark']),
    dict(issue=4340, sweep='config-plugins.ini', kind='exception', match='IsADirectoryError save_config',
         cases=['whole file: directory']),
    dict(issue=4340, sweep='config-plugins.ini', kind='incomplete', match='quit',
         cases=['whole file: directory']),
    dict(issue=4340, sweep='config-terminology.ini', kind='config-reset', match='',
         cases=['whole file: byte order mark']),
    dict(issue=4340, sweep='config-terminology.ini', kind='exception', match='IsADirectoryError save_config',
         cases=['whole file: directory']),
    dict(issue=4340, sweep='config-terminology.ini', kind='incomplete', match='quit',
         cases=['whole file: directory']),
    dict(issue=4340, sweep='config-tm.ini', kind='exception', match='AttributeError _configure_proxy',
         cases=['localtm.tmserver_bind: blank', 'localtm.tmserver_bind: space']),
    dict(issue=4340, sweep='config-tm.ini', kind='log-error', match='TypeError _launch_tmserver',
         cases=['localtm.tmserver_bind: brackets', 'localtm.tmserver_bind: comma', 'localtm.tmserver_bind: control', 'localtm.tmserver_bind: float', 'localtm.tmserver_bind: huge int', 'localtm.tmserver_bind: long', 'localtm.tmserver_bind: negative', 'localtm.tmserver_bind: newline', 'localtm.tmserver_bind: pair junk', 'localtm.tmserver_bind: percent', 'localtm.tmserver_bind: percent format', 'localtm.tmserver_bind: pipe', 'localtm.tmserver_bind: relative path']),
    dict(issue=4340, sweep='config-tm.ini', kind='log-error', match='ValueError __init__',
         cases=['localtm.tmserver_port: None', 'localtm.tmserver_port: RTL', 'localtm.tmserver_port: blank', 'localtm.tmserver_port: bool', 'localtm.tmserver_port: brackets', 'localtm.tmserver_port: comma', 'localtm.tmserver_port: control', 'localtm.tmserver_port: exponent', 'localtm.tmserver_port: float', 'localtm.tmserver_port: long', 'localtm.tmserver_port: newline', 'localtm.tmserver_port: non-ASCII', 'localtm.tmserver_port: one code', 'localtm.tmserver_port: pair junk', 'localtm.tmserver_port: percent', 'localtm.tmserver_port: percent format', 'localtm.tmserver_port: pipe', 'localtm.tmserver_port: relative path', 'localtm.tmserver_port: space', 'localtm.tmserver_port: word']),
    dict(issue=4340, sweep='config-tm.ini', kind='log-error', match='OverflowError test_port',
         cases=['localtm.tmserver_port: huge int', 'localtm.tmserver_port: negative']),
    dict(issue=4340, sweep='config-tm.ini', kind='timeout', match='test_port',
         cases=['localtm.tmserver_bind: None', 'localtm.tmserver_bind: RTL', 'localtm.tmserver_bind: bool', 'localtm.tmserver_bind: exponent', 'localtm.tmserver_bind: non-ASCII', 'localtm.tmserver_bind: one code', 'localtm.tmserver_bind: word']),
    # Raised in a signal handler or logged at plug-in load, depending on timing.
    dict(issue=4340, sweep='config-tm.ini', kind=['exception', 'log-error'], match='ValueError recreate_matcher',
         cases=['currentfile.max_length: None', 'currentfile.max_length: RTL', 'currentfile.max_length: blank', 'currentfile.max_length: bool', 'currentfile.max_length: brackets', 'currentfile.max_length: comma', 'currentfile.max_length: control', 'currentfile.max_length: exponent', 'currentfile.max_length: float', 'currentfile.max_length: long', 'currentfile.max_length: newline', 'currentfile.max_length: non-ASCII', 'currentfile.max_length: one code', 'currentfile.max_length: pair junk', 'currentfile.max_length: percent', 'currentfile.max_length: percent format', 'currentfile.max_length: pipe', 'currentfile.max_length: relative path', 'currentfile.max_length: space', 'currentfile.max_length: word']),
    dict(issue=4340, sweep='config-tm.ini', kind='exception', match='AttributeError _check_other_units',
         cases=ALL, strict=False),
    # Only when a TM query runs during the start-up.
    dict(issue=4340, sweep='config-plugins.ini', kind='exception', match='OverflowError matches',
         cases=['tm.max_matches: huge int'], strict=False),
    dict(issue=4340, sweep='config-tm.ini', kind='config-reset', match='',
         cases=['whole file: byte order mark']),
    dict(issue=4340, sweep='config-tm.ini', kind='exception', match='IsADirectoryError save_config',
         cases=['whole file: directory']),
    dict(issue=4340, sweep='config-tm.ini', kind='incomplete', match='quit',
         cases=['whole file: directory']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='exception', match='ValueError _restore_window_geometry',
         cases=['general.windowheight: None', 'general.windowheight: RTL', 'general.windowheight: blank', 'general.windowheight: bool', 'general.windowheight: brackets', 'general.windowheight: comma', 'general.windowheight: control', 'general.windowheight: exponent', 'general.windowheight: float', 'general.windowheight: long', 'general.windowheight: newline', 'general.windowheight: non-ASCII', 'general.windowheight: one code', 'general.windowheight: pair junk', 'general.windowheight: percent', 'general.windowheight: percent format', 'general.windowheight: pipe', 'general.windowheight: relative path', 'general.windowheight: space', 'general.windowheight: word', 'general.windowwidth: None', 'general.windowwidth: RTL', 'general.windowwidth: blank', 'general.windowwidth: bool', 'general.windowwidth: brackets', 'general.windowwidth: comma', 'general.windowwidth: control', 'general.windowwidth: exponent', 'general.windowwidth: float', 'general.windowwidth: long', 'general.windowwidth: newline', 'general.windowwidth: non-ASCII', 'general.windowwidth: one code', 'general.windowwidth: pair junk', 'general.windowwidth: percent', 'general.windowwidth: percent format', 'general.windowwidth: pipe', 'general.windowwidth: relative path', 'general.windowwidth: space', 'general.windowwidth: word']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='incomplete', match='start-up',
         cases=['general.windowheight: None', 'general.windowheight: RTL', 'general.windowheight: blank', 'general.windowheight: bool', 'general.windowheight: brackets', 'general.windowheight: comma', 'general.windowheight: control', 'general.windowheight: exponent', 'general.windowheight: float', 'general.windowheight: huge int', 'general.windowheight: long', 'general.windowheight: newline', 'general.windowheight: non-ASCII', 'general.windowheight: one code', 'general.windowheight: pair junk', 'general.windowheight: percent', 'general.windowheight: percent format', 'general.windowheight: pipe', 'general.windowheight: relative path', 'general.windowheight: space', 'general.windowheight: word', 'general.windowwidth: None', 'general.windowwidth: RTL', 'general.windowwidth: blank', 'general.windowwidth: bool', 'general.windowwidth: brackets', 'general.windowwidth: comma', 'general.windowwidth: control', 'general.windowwidth: exponent', 'general.windowwidth: float', 'general.windowwidth: huge int', 'general.windowwidth: long', 'general.windowwidth: newline', 'general.windowwidth: non-ASCII', 'general.windowwidth: one code', 'general.windowwidth: pair junk', 'general.windowwidth: percent', 'general.windowwidth: percent format', 'general.windowwidth: pipe', 'general.windowwidth: relative path', 'general.windowwidth: space', 'general.windowwidth: word']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='exception', match='OverflowError _restore_window_geometry',
         cases=['general.windowheight: huge int', 'general.windowwidth: huge int']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='critical', match="Gtk: gtk_window_resize: assertion 'width > 0' failed",
         cases=['general.windowwidth: negative', 'general.windowwidth: zero']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='critical', match="Gtk: gtk_window_resize: assertion 'height > 0' failed",
         cases=['general.windowheight: negative', 'general.windowheight: zero']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='exception', match='Error set_widget_font',
         cases=['language.sourcefont: newline', 'language.targetfont: newline']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='exception', match='ZeroDivisionError check_editor_height',
         cases=['language.sourcefont: newline']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='exception', match='IndexError do_start_editing',
         cases=['language.sourcefont: newline', 'language.targetfont: newline']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='exception', match='UnicodeEncodeError __init__',
         cases=['language.sourcelang: RTL', 'language.sourcelang: non-ASCII']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='config-reset', match='',
         cases=['whole file: byte order mark']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='log-error', match='IsADirectoryError write',
         cases=['whole file: directory']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='error-dialog', match='',
         cases=['whole file: directory']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='exception', match='IsADirectoryError write',
         cases=['whole file: directory']),
    dict(issue=4340, sweep='config-virtaal.ini', kind='incomplete', match='save',
         cases=['whole file: directory']),
    dict(issue=4340, sweep='config-weblookup.ini', kind='config-reset', match='',
         cases=['whole file: byte order mark']),
    dict(issue=4340, sweep='config-weblookup.ini', kind='log-error', match='KeyError _load_urldata',
         cases=['whole file: 5 MB']),
    dict(issue=4340, sweep='config-weblookup.ini', kind='exception', match='KeyError ',
         cases=['whole file: 5 MB']),
    dict(issue=4340, sweep='config-weblookup.ini', kind='incomplete', match='look-up',
         cases=['whole file: 5 MB']),
    dict(issue=4340, sweep='config-weblookup.ini', kind='exception', match='IsADirectoryError save_config',
         cases=['whole file: directory']),
    dict(issue=4340, sweep='config-weblookup.ini', kind='incomplete', match='quit',
         cases=['whole file: directory']),
    dict(issue=4397, sweep='config-virtaal.ini', kind='glib-warning', platforms=['linux'], strict=False, match='Gdk: Native Windows wider or taller than 32767 pixels are not supported',
         cases=['language.sourcelang: long']),
    dict(issue=4431, sweep='data', kind=['exception', 'log-error'], match='XMLSyntaxError load_dictionary',
         cases=['autocorrect: binary', 'autocorrect: empty', 'autocorrect: truncated']),
    dict(issue=4431, sweep='data', kind='exception', match='ValueError load_dictionary',
         cases=['autocorrect: XLIFF content']),
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
    # Windows' GtkSpell finishes in time.
    dict(issue=4443, sweep='spelling', kind='timeout', match='', cases=['100k chars'], platforms=['linux', 'macos']),
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
