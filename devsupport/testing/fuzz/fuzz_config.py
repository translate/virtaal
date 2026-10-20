#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Start-up fuzzer: one fresh Virtaal per case, with one config value, a
whole config file, or one of the data files Virtaal keeps replaced by
something broken.

Each start-up opens a file, moves a unit, saves, builds the look-up menu
and quits. A case fails on an exception, a logged error, a critical, an
error dialog, a start-up that doesn't get through those steps, or a
config file reset that the file's content doesn't call for. Results are
matched against known_bugs.py, as in fuzz_ui.py. Linux only for now: the
config location comes from HOME.

    python devsupport/testing/fuzz/fuzz_config.py [--results DIR] [--jobs N]
        [--only SWEEP]
"""

import argparse
import configparser
import glob
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fuzz_ui  # noqa: E402
import results  # noqa: E402
from malformed import PO  # noqa: E402

CASE_TIMEOUT = 60
KILL_AFTER = 75

VALUES = [
    ('blank', ''), ('space', '   '), ('word', 'abc'), ('negative', '-1'), ('zero', '0'),
    ('float', '1.5'), ('huge int', '99999999999999999999'), ('exponent', '1e9'), ('None', 'None'),
    ('bool', 'True'), ('non-ASCII', 'Ünï中文\U0001f44d'), ('percent', '%'),
    ('percent format', '%(x)s %s'), ('comma', ','), ('pipe', '|'), ('pair junk', 'en,|,af,de'),
    ('one code', 'en'), ('relative path', '../../nonexistent/dir'), ('long', 'x' * 20000),
    ('newline', 'a\nb'), ('brackets', '[x]'), ('control', 'a\x01b'), ('RTL', 'مرحبا'),
]

INI_KEYS = [
    ('plugins.ini', 'tm', 'max_matches'), ('plugins.ini', 'tm', 'min_quality'),
    ('plugins.ini', 'tm', 'disabled_models'), ('plugins.ini', 'tm', 'backends_dialog_width'),
    ('plugins.ini', 'terminology', 'max_matches'), ('plugins.ini', 'terminology', 'min_quality'),
    ('plugins.ini', 'terminology', 'disabled_models'),
    ('plugins.ini', 'lookup', 'disabled_models'), ('plugins.ini', 'lookup', 'backends_dialog_width'),
    ('tm.ini', 'localtm', 'tmserver_bind'), ('tm.ini', 'localtm', 'tmserver_port'),
    ('tm.ini', 'localtm', 'tmdb'), ('tm.ini', 'currentfile', 'max_length'),
    ('terminology.ini', 'localfile', 'files'), ('terminology.ini', 'localfile', 'extendfile'),
    ('weblookup.ini', 'custom', 'display_name'), ('weblookup.ini', 'custom', 'url'),
    ('weblookup.ini', 'custom', 'quoted'), ('weblookup.ini', 'custom', 'enabled'),
    ('weblookup.ini', 'custom', 'id'),
    ('langs.ini', 'fz', 'name'), ('langs.ini', 'fz', 'nplurals'), ('langs.ini', 'fz', 'plural'),
]

# Sections a key case needs filled in around the key under test.
SECTION_DEFAULTS = {
    ('weblookup.ini', 'custom'): {'display_name': 'Custom', 'url': 'https://example.org/%(query)s',
                                  'quoted': 'False', 'enabled': 'True', 'id': 'custom'},
    ('langs.ini', 'fz'): {'name': 'Fuzzish', 'nplurals': '2', 'plural': '(n != 1)'},
}

INI_FILES = ['virtaal.ini', 'plugins.ini', 'tm.ini', 'terminology.ini', 'weblookup.ini', 'langs.ini']

# label, content, whether resetting the file (with a backup) is the right answer
WHOLE_FILE = [
    ('empty file', b'', False),
    ('binary garbage', bytes(range(256)) * 4, True),
    ('invalid UTF-8', b'[general]\nlastdir = \xff\xfe\xfa\n', True),
    ('byte order mark', b'\xef\xbb\xbf[general]\nwindowwidth = 800\n', False),
    ('no section header', b'name = x\n', True),
    ('duplicate section', b'[general]\na = 1\n[general]\nb = 2\n', True),
    ('duplicate key', b'[general]\nwindowwidth = 1\nwindowwidth = 2\n', True),
    ('only comments', b'; hi\n# there\n', False),
    ('5 MB', b'[general]\nx = ' + b'y' * 5000000 + b'\n', False),
    ('directory', None, True),
]


def _sqlite(path, schema, rows=0):
    db = sqlite3.connect(path)
    db.execute(schema)
    for i in range(rows):
        db.execute('INSERT INTO t VALUES (?)', ('x' * 100 + str(i),))
    db.commit()
    db.close()
    with open(path, 'rb') as f:
        return f.read()


def _db_variants(tmp):
    path = os.path.join(tmp, 'v.db')
    full = _sqlite(path, 'CREATE TABLE t (x TEXT)', rows=500)
    os.remove(path)
    return [
        ('empty', b''),
        ('not SQLite', b'hello\n' * 100),
        ('truncated', full[:len(full) // 2]),
        ('other schema', full),
        ('directory', None),
    ]


def config_dir(home):
    return fuzz_ui.config_dir(home)


def data_cases(tmp):
    """(case, relative path from home, content, plug-in settings to switch on,
    whether a logged error is the right answer)"""
    conf = os.path.relpath(config_dir('/h'), '/h')
    out = []
    for label, content in _db_variants(tmp):
        out.append(('tm.db: ' + label, os.path.join(conf, 'tm.db'), content, {}, False))
        out.append(('stats.db: ' + label, os.path.join('.translate_toolkit', 'stats.db'), content, {}, False))
    junk = [('empty', b''), ('binary', bytes(range(256)) * 8), ('truncated', PO[:len(PO) // 2]),
            ('XLIFF content', b'<?xml version="1.0"?><xliff version="1.2"><file><body/></file></xliff>')]
    # A glossary that can't be read is logged and left out.
    for label, content in junk + [('directory', None)]:
        out.append(('terminology.po: ' + label, os.path.join(conf, 'terminology.po'), content, {}, True))
    for label, content in junk:
        out.append(('autoterm: ' + label, os.path.join(conf, 'autoterm', 'en__af.po'), content,
                    {('plugins.ini', 'terminology', 'disabled_models'): 'pontoon'}, False))
        out.append(('thesaurus: ' + label, os.path.join(conf, 'thesaurus', 'af', 'th_af.dat'), content,
                    {('plugins.ini', 'lookup', 'disabled_models'): ''}, False))
        out.append(('autocorrect: ' + label, os.path.join(conf, 'autocorr', 'af', 'DocumentList.xml'), content,
                    {('virtaal.ini', 'plugin_state', 'autocorrector'): 'enabled'}, False))
    return out


def virtaal_ini_keys():
    """Every key of virtaal.ini, read from Settings in a throwaway home."""
    home = tempfile.mkdtemp(prefix='virtaal-fuzz-keys-')
    os.environ['HOME'] = home
    os.environ['APPDATA'] = os.path.join(home, 'AppData')
    sys.path.insert(1, os.path.abspath(os.path.join(HERE, '..', '..', '..')))
    from virtaal.common import pan_app
    keys = []
    for section in pan_app.Settings.sections:
        for key in getattr(pan_app.Settings, section):
            # Anything but 'disabled' enables a demo plug-in whose modal
            # dialog stops start-up.
            if key != '_helloworld':
                keys.append(('virtaal.ini', section, key))
    shutil.rmtree(home, ignore_errors=True)
    return keys + [('virtaal.ini', 'plugin_state', 'tm')]


def all_cases(tmp):
    cases = []
    for name, section, key in virtaal_ini_keys() + INI_KEYS:
        for label, value in VALUES:
            cases.append({'sweep': 'config-' + name, 'case': '%s.%s: %s' % (section, key, label),
                          'file': name, 'section': section, 'key': key, 'value': value})
    for name in INI_FILES:
        for label, content, reset_ok in WHOLE_FILE:
            cases.append({'sweep': 'config-' + name, 'case': 'whole file: ' + label, 'file': name,
                          'content': None if content is None else content.hex(), 'reset_ok': reset_ok})
    for label, path, content, settings, log_ok in data_cases(tmp):
        cases.append({'sweep': 'data', 'case': label, 'path': path, 'log_ok': log_ok,
                      'content': None if content is None else content.hex(),
                      'settings': [[f, s, k, v] for (f, s, k), v in settings.items()]})
    return cases


def _set(conf, name, section, key, value):
    path = os.path.join(conf, name)
    parser = configparser.RawConfigParser()
    if os.path.isfile(path):
        parser.read(path, encoding='utf-8')
    if not parser.has_section(section):
        parser.add_section(section)
    for k, v in SECTION_DEFAULTS.get((name, section), {}).items():
        if not parser.has_option(section, k):
            parser.set(section, k, v)
    parser.set(section, key, value)
    with open(path, 'w', encoding='utf-8') as f:
        parser.write(f)


def _write(path, content_hex):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if content_hex is None:
        os.makedirs(path)
    else:
        with open(path, 'wb') as f:
            f.write(bytes.fromhex(content_hex))


def apply_case(home, case, port):
    conf = config_dir(home)
    # Parallel start-ups would all try the TM server's default port.
    _set(conf, 'tm.ini', 'localtm', 'tmserver_port', str(port))
    if 'key' in case:
        _set(conf, case['file'], case['section'], case['key'], case['value'])
    elif 'file' in case:
        _write(os.path.join(conf, case['file']), case['content'])
    else:
        for name, section, key, value in case['settings']:
            _set(conf, name, section, key, value)
        _write(os.path.join(home, case['path']), case['content'])


# ONE START-UP (in the child) #

def child(case_path, results_path):
    with open(case_path, encoding='utf-8') as f:
        case = json.load(f)
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import GLib
    from record import Recorder
    sys.path.insert(1, os.path.abspath(os.path.join(HERE, '..', '..', '..')))

    recorder = Recorder(results_path, CASE_TIMEOUT, slow_seconds=None)
    recorder.install()
    recorder.begin(case['sweep'], case['case'])
    home = os.environ['HOME']
    done = []

    def finish():
        steps = ['start-up', 'open', 'move', 'save', 'look-up', 'quit']
        if done != steps:
            missing = [step for step in steps if step not in done]
            recorder.problem('incomplete', missing[0], 'did not get through: %s' % ', '.join(missing))
        backups = glob.glob(os.path.join(config_dir(home), '*.broken*'))
        if backups and not case.get('reset_ok'):
            recorder.problem('config-reset', '', 'backed up and reset: %s' % ', '.join(
                os.path.basename(b) for b in backups))
        recorder.done()
        os._exit(0)

    try:
        from virtaal.main import Virtaal
        app = Virtaal('')
        mc = app.main_controller
        sys.excepthook = recorder.exception
        recorder.stub_dialogs(mc)
        done.append('start-up')
    except Exception:
        recorder.exception(*sys.exc_info())
        finish()

    def step(name, call):
        """False from the call is a failure the app already reported."""
        try:
            if call() is not False:
                done.append(name)
        except Exception:
            recorder.exception(*sys.exc_info())

    def driver():
        for _ in range(10):
            yield
        steps = [
            ('open', lambda: mc.open_file(os.path.join(home, 'files', 'target.po'))),
            ('move', lambda: mc.store_controller.cursor.force_index(1)),
            ('save', lambda: mc.store_controller.set_modified(True) or mc.save_file()),
            ('look-up', lambda: mc.plugin_controller.plugins['lookup'].controller.plugin_controller
             .plugins['weblookup'].create_menu_items('word', 'source', 'en', 'af', None)),
        ]
        for name, call in steps:
            step(name, call)
            for _ in range(15):
                yield
        # quit() returns False as an idle callback does, not as a failure.
        step('quit', lambda: mc.quit(force=True) or None)
        for _ in range(15):
            yield
        finish()

    steps = driver()
    GLib.timeout_add(20, lambda: next(steps, False) is not False)
    try:
        app.run()
    except Exception:
        recorder.exception(*sys.exc_info())
    finish()


# THE PARENT #

def run(cases, outdir, jobs):
    base = fuzz_ui.prepare_home(os.path.join(outdir, 'base'))
    os.makedirs(os.path.join(base, 'files'))
    with open(os.path.join(base, 'files', 'target.po'), 'wb') as f:
        f.write(PO)
    scratch = os.path.join(outdir, 'cases')
    os.makedirs(scratch)
    found = []
    running = []

    def collect(proc, case, home, started):
        killed = False
        try:
            proc.wait(timeout=max(1, KILL_AFTER - (time.monotonic() - started)))
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            killed = True
        with open(os.path.join(home, 'stderr'), encoding='utf-8', errors='replace') as f:
            stderr = f.read()
        cases_found, finished, stderr = fuzz_ui.parse_child(os.path.join(home, 'results.jsonl'), stderr)
        own = [c for c in cases_found if c['case'] == case['case']]
        if not finished:
            problem = ({'kind': 'timeout', 'signature': '', 'detail': stderr[-3000:]} if killed
                       else fuzz_ui.died_in(cases_found, stderr))
            if own:
                own[0]['problems'].append(problem)
            else:
                cases_found.append({'sweep': case['sweep'], 'case': case['case'], 'elapsed': 0, 'problems': [problem]})
        for result in cases_found:
            if case.get('log_ok'):
                result['problems'] = [p for p in result['problems'] if p['kind'] != 'log-error']
            if result['case'] != case['case'] and not result['problems']:
                continue
            found.append(result)
        shutil.rmtree(home, ignore_errors=True)

    for i, case in enumerate(cases):
        while len(running) >= jobs:
            for item in list(running):
                if item[0].poll() is not None or time.monotonic() - item[3] > KILL_AFTER:
                    running.remove(item)
                    collect(*item)
            time.sleep(0.2)
        home = os.path.join(scratch, str(i), 'home')
        shutil.copytree(base, home, symlinks=True)
        for ini in glob.glob(os.path.join(config_dir(home), '*.ini')):
            with open(ini, encoding='utf-8') as f:
                text = f.read().replace(base, home)
            with open(ini, 'w', encoding='utf-8') as f:
                f.write(text)
        apply_case(home, case, 56000 + i % 1000)
        case_path = os.path.join(home, '..', 'case.json')
        with open(case_path, 'w', encoding='utf-8') as f:
            json.dump(case, f)
        child_env = fuzz_ui.child_env(home)
        stderr = open(os.path.join(home, 'stderr'), 'w')
        # A relative path in a value lands in the working directory.
        proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), '--child', case_path,
                                 '--results', os.path.join(home, 'results.jsonl')],
                                env=child_env, cwd=os.path.dirname(home), stdout=stderr, stderr=stderr)
        running.append((proc, case, home, time.monotonic()))
    for item in running:
        collect(*item)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--results', default=None, help='Directory for results (default: a new temp dir).')
    parser.add_argument('--jobs', type=int, default=8, help='Start-ups to run at once (default: 8).')
    parser.add_argument('--only', default=None, help='Run only this sweep, e.g. config-tm.ini or data.')
    parser.add_argument('--child', default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        child(args.child, args.results)
        return 0

    outdir = os.path.abspath(args.results or tempfile.mkdtemp(prefix='virtaal-fuzz-config-'))
    os.makedirs(outdir, exist_ok=True)
    platform = results.current_platform()
    cases = all_cases(outdir)
    if args.only:
        cases = [c for c in cases if c['sweep'] == args.only]
    print('%d start-ups, %d at a time, results in %s' % (len(cases), args.jobs, outdir), flush=True)
    start = time.monotonic()
    found = run(cases, outdir, args.jobs)
    print('done in %.0f s' % (time.monotonic() - start), flush=True)
    for path in ('base', 'cases'):
        shutil.rmtree(os.path.join(outdir, path), ignore_errors=True)
    return fuzz_ui.report(found, outdir, platform)


if __name__ == '__main__':
    sys.exit(main())
