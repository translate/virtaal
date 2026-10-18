#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""UI fuzzer: a corpus sweep of every text input, then random interaction.

The sweep (sweep.py) puts every corpus value through every text input in
a fixed order, and opens and saves malformed files and awkward paths. The
random part then drives the real controllers
(navigate, switch mode, edit with corpus text, search, undo, save,
close/reopen, resize) for --duration-seconds, after native crashes and
timing problems, such as a live GTK object graph torn down in a way that
isn't safe against Python's garbage collection.

Both run as child processes with an isolated, offline config. This
process matches their failures against known_bugs.py and writes a summary
(also to $GITHUB_STEP_SUMMARY). Exit status 1 means a new failure, or a
known-bug entry that is stale (its failure didn't happen) or whose issue
is closed - see results.py.

Usage:
    python devsupport/testing/fuzz/fuzz_ui.py [--duration-seconds N | --iterations N]
        [--seed N] [--sections LIST] [--no-sweep] [--no-random]
        [--results DIR] [--debugger gdb|lldb]

A GTK critical has no Python stack. To find where one comes from, replay
the run's seed with G_DEBUG=fatal-criticals: the first critical then
stops the process and the stack is in the results directory.
"""

import argparse
import faulthandler
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)

import results  # noqa: E402
from known_bugs import KNOWN_BUGS  # noqa: E402
from record import (  # noqa: E402
    GLIB_IGNORE,
    OUTSIDE_CASE,
    STDERR_MARKER,
    TIMEOUT_MARKER,
    is_virtaal_path,
)
from sweep import SECTIONS  # noqa: E402

TESTFILES_DIR = os.path.join(REPO_ROOT, 'devsupport', 'testfiles')
DEFAULT_TESTFILES = ['workflow.po', 'workflow.xliff', 'workflow.ts', 'checks.po']
CASE_TIMEOUT = 60
# A known freeze takes 11 s to minutes depending on the runner; a fix makes
# it take well under a second.
FREEZE_LIMIT = 8
MAX_RESTARTS = 20
DEBUGGERS = {
    'gdb': ['gdb', '-q', '--batch', '-ex', 'run', '-ex', 'thread apply all bt full', '--args'],
    'lldb': ['lldb', '-b', '-k', 'bt all', '-k', 'quit', '-o', 'process launch', '-o', 'continue', '--'],
}


# ISOLATED CONFIG #

def config_dir(home):
    if sys.platform.startswith('win'):
        return os.path.join(home, 'AppData', 'Virtaal')
    if sys.platform == 'darwin':
        return os.path.join(home, 'Library', 'Application Support', 'Virtaal')
    return os.path.join(home, '.virtaal')


def prepare_home(root):
    """A fresh home whose Virtaal config turns off everything that uses
    the network or isn't under test."""
    home = os.path.join(root, 'home')
    conf = config_dir(home)
    os.makedirs(conf)
    with open(os.path.join(conf, 'virtaal.ini'), 'w', encoding='utf-8') as f:
        f.write('[language]\nsourcelang = en\ntargetlang = af\n'
                '[translator]\nname = Fuzz Tester\nemail = fuzz@example.org\nteam = af@example.org\n'
                '[plugin_state]\nspellchecker = disabled\nautocorrector = disabled\n'
                '_ipython_console = disabled\n_python_console = disabled\n')
    with open(os.path.join(conf, 'plugins.ini'), 'w', encoding='utf-8') as f:
        f.write('[terminology]\ndisabled_models = autoterm,pontoon\n'
                '[tm]\ndisabled_models = _dummytm,remotetm,apertium,google_translate,moses,amagama\n'
                '[lookup]\ndisabled_models = thesaurus\n')
    glossary = os.path.join(conf, 'terminology.po')
    with open(glossary, 'w', encoding='utf-8') as f:
        f.write('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n"Language: af\\n"\n\n'
                'msgid "file"\nmsgstr "l\u00eaer"\n')
    with open(os.path.join(conf, 'terminology.ini'), 'w', encoding='utf-8') as f:
        f.write('[localfile]\nfiles = %s\nextendfile = %s\n' % (glossary, glossary))
    return home


def child_env(home):
    env = dict(os.environ)
    env['HOME'] = home
    env['APPDATA'] = os.path.join(home, 'AppData')
    env['PYTHONFAULTHANDLER'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    # No accessibility bus under Xvfb; GTK would warn about it at start-up.
    env['NO_AT_BRIDGE'] = '1'
    # Anything that still tries the network fails fast instead of
    # making results depend on it; the local TM server stays reachable.
    for name in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
        env[name] = 'http://127.0.0.1:9'
    env['no_proxy'] = env['NO_PROXY'] = 'localhost,127.0.0.1'
    return env


# CHILD PROCESSES #

def run_child(args, env, outdir, name, debugger, limit):
    """Run a child; returns (results, finished, stderr text)."""
    results_path = os.path.join(outdir, name + '.jsonl')
    stderr_path = os.path.join(outdir, name + '.stderr')
    stdout_path = os.path.join(outdir, name + '.log')
    if os.path.exists(results_path):
        os.remove(results_path)
    command = DEBUGGERS.get(debugger, []) + [sys.executable] + args + ['--results', results_path]
    with open(stdout_path, 'w') as out, open(stderr_path, 'w') as err:
        try:
            subprocess.run(command, env=env, stdout=out, stderr=err, timeout=limit)
        except subprocess.TimeoutExpired:
            pass
    with open(stderr_path, encoding='utf-8', errors='replace') as f:
        stderr = f.read()
    with open(stdout_path, encoding='utf-8', errors='replace') as f:
        stderr += f.read()  # a debugger's backtrace goes to stdout
    return parse_child(results_path, stderr)


def _glib_line(line):
    for level, kind in (('-CRITICAL **', 'critical'), ('-ERROR **', 'critical'), ('-WARNING **', 'glib-warning')):
        if level in line and not any(text in line for text in GLIB_IGNORE):
            message = line.split('**:', 1)[-1].strip()
            # Drop the timestamp GLib puts first.
            parts = message.split(': ', 1)
            if len(parts) == 2 and parts[0].replace(':', '').replace('.', '').isdigit():
                message = parts[1]
            domain = line.split(level)[0].rsplit(' ', 1)[-1]
            return kind, '%s: %s' % (domain, message[:120]), line.strip()
    return None


def parse_child(results_path, stderr):
    """Cases from a child's results file, plus the GLib warnings it wrote
    to stderr, each attributed to the case running at the time."""
    found = []
    by_key = {}
    open_case = None
    finished = False
    if os.path.exists(results_path):
        with open(results_path, encoding='utf-8') as f:
            for line in f:
                event = json.loads(line)
                if event['event'] == 'begin':
                    open_case = {'sweep': event['sweep'], 'case': event['case'], 'problems': [], 'elapsed': None}
                    found.append(open_case)
                    by_key[(event['sweep'], event['case'])] = open_case
                elif event['event'] == 'problem' and open_case is not None:
                    open_case['problems'].append({k: event[k] for k in ('kind', 'signature', 'detail')})
                elif event['event'] == 'end' and open_case is not None:
                    open_case['elapsed'] = event['elapsed']
                    open_case = None
                elif event['event'] == 'done':
                    finished = True

    current = None
    for line in stderr.splitlines():
        if line.startswith(STDERR_MARKER):
            event = json.loads(line[len(STDERR_MARKER):])
            if event['event'] == 'begin':
                current = by_key.get((event['sweep'], event['case']))
            elif event['event'] == 'end':
                current = None
            continue
        glib = _glib_line(line)
        if glib:
            kind, signature, detail = glib
            if current is None:
                current = {'sweep': found[-1]['sweep'] if found else 'setup', 'case': OUTSIDE_CASE,
                           'problems': [], 'elapsed': 0}
                found.append(current)
            current['problems'].append({'kind': kind, 'signature': signature, 'detail': detail})
    return found, finished, stderr


def died_in(cases, stderr):
    """The problem for a child that ended mid-case: a timeout (faulthandler
    dumped the stacks) or a crash."""
    after = stderr.rsplit(STDERR_MARKER, 1)[-1]
    if TIMEOUT_MARKER not in after:
        return {'kind': 'crash', 'signature': '', 'detail': after[-3000:]}
    # A debugger's own output can follow the dump; keep the dump.
    dump = after[after.index(TIMEOUT_MARKER):][:3000]
    frames = re.findall(r'File "([^"]+)", line \d+ in (\w+)', dump)
    own = [name for path, name in frames if is_virtaal_path(path)]
    return {'kind': 'timeout', 'signature': own[0] if own else '', 'detail': dump}


def run_section(section, env, outdir, debugger, platform):
    """Every case of a section, restarting after a case that kills the
    process; known freezes run alone with a short time limit."""
    sweeps = SECTIONS[section]
    freezes = [(sweep, case) for entry in map(results.normalize, KNOWN_BUGS)
               if entry['kind'] == 'timeout' and platform in entry['platforms']
               for sweep in entry['sweeps'] if sweep in sweeps
               for case in entry['cases']]
    collected = []
    skip = set(freezes)
    workdir = os.path.join(outdir, section + '-files')
    os.makedirs(workdir, exist_ok=True)
    for attempt in range(MAX_RESTARTS):
        skip_file = os.path.join(outdir, '%s-skip.json' % section)
        with open(skip_file, 'w', encoding='utf-8') as f:
            json.dump(sorted(skip), f)
        cases, finished, stderr = run_child(
            [os.path.join(HERE, 'sweep.py'), section, '--workdir', workdir, '--skip-file', skip_file,
             '--case-timeout', str(CASE_TIMEOUT)],
            env, outdir, '%s-%d' % (section, attempt), debugger, limit=3600)
        collected += cases
        skip |= {(c['sweep'], c['case']) for c in cases}
        if finished:
            break
        unfinished = [c for c in cases if c['elapsed'] is None]
        if unfinished:
            unfinished[-1]['problems'].append(died_in(cases, stderr))
        else:
            collected.append({'sweep': sweeps[0], 'case': OUTSIDE_CASE, 'elapsed': 0,
                              'problems': [died_in(cases, stderr)]})
            break

    for sweep, case in freezes:
        cases, finished, stderr = run_child(
            [os.path.join(HERE, 'sweep.py'), section, '--workdir', workdir, '--only', '%s/%s' % (sweep, case),
             '--case-timeout', str(FREEZE_LIMIT)],
            env, outdir, '%s-freeze-%s' % (sweep, case.replace(' ', '_').replace('/', '_')), debugger,
            limit=FREEZE_LIMIT + 300)
        own = [c for c in cases if c['case'] == case]
        if own and own[-1]['elapsed'] is None:
            own[-1]['problems'].append(died_in(cases, stderr))
        elif not own:
            problem = died_in(cases, stderr) if not finished else {
                'kind': 'not-run', 'signature': '', 'detail': 'the case never started'}
            cases.append({'sweep': sweep, 'case': case, 'elapsed': 0, 'problems': [problem]})
        collected += cases
    return [c for c in collected if c['case'] != OUTSIDE_CASE or c['problems']]


def run_random(args, env, outdir, debugger):
    child_args = [os.path.abspath(__file__), '--random-child', '--seed', str(args.seed),
                  '--log', args.log, '--case-timeout', str(CASE_TIMEOUT)]
    if args.duration_seconds:
        child_args += ['--duration-seconds', str(args.duration_seconds)]
        limit = args.duration_seconds * 2 + 300
    else:
        child_args += ['--iterations', str(args.iterations)]
        limit = 3600
    cases, finished, stderr = run_child(child_args, env, outdir, 'random', debugger, limit)
    if not finished:
        unfinished = [c for c in cases if c['elapsed'] is None]
        if unfinished:
            unfinished[-1]['problems'].append(died_in(cases, stderr))
        else:
            cases.append({'sweep': 'random', 'case': OUTSIDE_CASE, 'elapsed': 0,
                          'problems': [died_in(cases, stderr)]})
    print('random part: %d actions' % len(cases))
    return [c for c in cases if c['problems']]


# THE RANDOM PART (in the child) #

class Fuzzer:
    def __init__(self, seed, log_path, recorder):
        from corpus import CORPUS
        from gi.repository import Gtk

        from virtaal.common import pan_app
        from virtaal.controllers.checkscontroller import ChecksController
        from virtaal.controllers.langcontroller import LanguageController
        from virtaal.controllers.maincontroller import MainController
        from virtaal.controllers.modecontroller import ModeController
        from virtaal.controllers.placeablescontroller import PlaceablesController
        from virtaal.controllers.storecontroller import StoreController
        from virtaal.controllers.undocontroller import UndoController
        from virtaal.controllers.unitcontroller import UnitController

        self.Gtk = Gtk
        self.corpus = CORPUS
        self.rng = random.Random(seed)
        self.rec = recorder
        self.testfiles = [os.path.join(TESTFILES_DIR, name) for name in DEFAULT_TESTFILES
                          if os.path.exists(os.path.join(TESTFILES_DIR, name))]
        if not self.testfiles:
            raise RuntimeError('No test fixtures found under %s' % TESTFILES_DIR)
        self._log_file = open(log_path, 'a', buffering=1, encoding='utf-8', errors='backslashreplace')
        self._tempdir = tempfile.mkdtemp(prefix='virtaal-fuzz-')
        self.iteration = 0

        # Avoids StoreModel._update_header()'s modal save-time prompt.
        pan_app.settings.translator['name'] = 'Fuzzer'
        pan_app.settings.translator['email'] = 'fuzzer@example.com'
        pan_app.settings.translator['team'] = 'none'

        # Same construction order as virtaal/test/test_scaffolding.py.
        self.main_controller = MainController()
        self.store_controller = StoreController(self.main_controller)
        self.unit_controller = UnitController(self.store_controller)
        self.undo_controller = UndoController(self.main_controller)
        self.mode_controller = ModeController(self.main_controller)
        self.checks_controller = ChecksController(self.main_controller)
        self.lang_controller = LanguageController(self.main_controller)
        # The target text box needs it to edit, as in the app.
        self.placeables_controller = PlaceablesController(self.main_controller)
        recorder.stub_dialogs(self.main_controller)
        # A mapped, realized window, as in real use: without one every
        # widget is an in-memory object with no window-server surface,
        # which can't reproduce native teardown races. MainView.show()
        # would also run Gtk.main(); step() pumps the loop itself.
        self.main_controller.view.main_window.show()
        self.store_controller.open_file(self.rng.choice(self.testfiles))
        self._load_current_unit()

        # weight, name, action
        self.actions = [
            (30, 'navigate', self._act_navigate),
            (15, 'switch_mode', self._act_switch_mode),
            (15, 'edit_target', self._act_edit_target),
            (10, 'search', self._act_search),
            (10, 'undo', self._act_undo),
            (5, 'redo', self._act_redo),
            (10, 'save_temp', self._act_save_temp),
            (10, 'close_reopen', self._act_close_reopen),
            (10, 'resize_window', self._act_resize_window),
            (10, 'advance_state', self._act_advance_state),
        ]

    def log(self, message):
        line = '%s [%d] %s' % (time.strftime('%H:%M:%S'), self.iteration, message)
        print(line)
        self._log_file.write(line + '\n')

    def _corpus_value(self):
        _, name, value = self.rng.choice(self.corpus)
        return name, value

    # ACTIONS #
    # Each calls the controller methods the matching menu item, shortcut
    # or click ends up calling.

    def _load_current_unit(self):
        # Real navigation loads the unit for editing through the treeview's
        # cell renderer, which isn't drawn here.
        cursor = self.store_controller.cursor
        unit = cursor and cursor.deref()
        if unit is not None:
            self.store_controller.get_unit_celleditor(unit)

    def _act_navigate(self):
        cursor = self.store_controller.cursor
        if cursor is None:
            return
        cursor.move(self.rng.choice([-100, -5, -1, 1, 5, 100]))
        self._load_current_unit()

    def _act_switch_mode(self):
        self.mode_controller.select_mode_by_name(self.rng.choice(list(self.mode_controller.modes.keys())))

    def _act_edit_target(self):
        unit = self.store_controller.cursor and self.store_controller.cursor.deref()
        if unit is None or not self.unit_controller.view.targets:
            return
        name, value = self._corpus_value()
        self.log('  corpus: %s' % name)
        buf = self.unit_controller.view.targets[0].buffer
        # Appending without limit makes later edits time out on sheer size.
        if self.rng.random() < 0.5 or buf.get_char_count() > 10000:
            buf.select_range(buf.get_start_iter(), buf.get_end_iter())
            buf.delete_selection(True, True)
        buf.insert_interactive_at_cursor(value, -1, True)

    def _act_search(self):
        self.mode_controller.select_mode_by_name('Search')
        mode = self.mode_controller.modes['Search']
        name, value = self._corpus_value()
        self.log('  corpus: %s' % name)
        mode.chk_regex.set_active(self.rng.random() < 0.5)
        mode.ent_search.set_text(value)
        mode._on_entry_activate(mode.ent_search)
        mode._on_search_next()

    def _act_undo(self):
        self.undo_controller._on_undo_activated()

    def _act_redo(self):
        self.undo_controller._on_redo_activated()

    def _act_save_temp(self):
        if self.store_controller.store is None:
            return
        ext = os.path.splitext(self.store_controller.get_store_filename() or '.po')[1] or '.po'
        self.store_controller.save_file(os.path.join(self._tempdir, 'fuzz-save-%d%s' % (self.iteration, ext)))

    def _act_close_reopen(self):
        self.store_controller.close_file()
        self.store_controller.open_file(self.rng.choice(self.testfiles))
        self._load_current_unit()

    def _act_resize_window(self):
        self.main_controller.view.main_window.resize(self.rng.randint(300, 1200), self.rng.randint(200, 900))

    def _act_advance_state(self):
        # Ctrl+Enter/Ctrl+Shift+Enter and the Navigation menu items.
        unit = self.store_controller.cursor and self.store_controller.cursor.deref()
        if unit is None:
            return
        self._load_current_unit()
        self.unit_controller.view.advance_workflow_state(self.rng.choice([1, -1]))

    # RUN LOOP #

    def step(self):
        self.iteration += 1
        total = sum(weight for weight, _, _ in self.actions)
        pick = self.rng.uniform(0, total)
        upto = 0
        for weight, name, action in self.actions:
            upto += weight
            if pick <= upto:
                break
        self.log(name)
        self.rec.begin('random', name)
        try:
            action()
        except Exception:
            self.rec.exception(*sys.exc_info())
        # Run what the action deferred (idle/timeout callbacks, signals)
        # before the next one, as in a real session. A repeating idle
        # callback keeps events pending for ever, so stop after a while.
        deadline = time.monotonic() + 2
        while self.Gtk.events_pending() and time.monotonic() < deadline:
            self.Gtk.main_iteration()
        self.rec.end()

    def run(self, iterations=None, duration_seconds=None):
        start = time.monotonic()
        count = 0
        while True:
            if iterations is not None and count >= iterations:
                break
            if duration_seconds is not None and time.monotonic() - start >= duration_seconds:
                break
            self.step()
            count += 1
        self.log('completed %d iterations' % count)


def random_child(args):
    import gi
    gi.require_version('Gtk', '3.0')
    sys.path.insert(1, REPO_ROOT)
    from record import Recorder

    recorder = Recorder(args.results, args.case_timeout, slow_seconds=None)
    recorder.sweep = 'random'
    recorder.install()
    fuzzer = Fuzzer(args.seed, args.log, recorder)
    fuzzer.run(iterations=None if args.duration_seconds else args.iterations,
               duration_seconds=args.duration_seconds)
    recorder.done()


def report(found, outdir, platform):
    """Write results.json and the summary; the exit status for the run."""
    with open(os.path.join(outdir, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump(found, f, indent=1)
    outcome = results.classify(found, KNOWN_BUGS, platform)
    issue_check = True
    if os.environ.get('GITHUB_ACTIONS'):
        states = results.fetch_issue_states([e['issue'] for e in KNOWN_BUGS if e.get('issue')],
                                            token=os.environ.get('GITHUB_TOKEN'))
        issue_check = bool(states)
        results.check_closed(outcome, KNOWN_BUGS, states)
    text = results.summary(outcome, platform, issue_check)
    print(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(text)
    return 1 if outcome.failed else 0


# MAIN #

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--iterations', type=int, default=500,
                        help='Random actions to perform (default: 500). Ignored with --duration-seconds.')
    parser.add_argument('--duration-seconds', type=int, default=None,
                        help='Run the random part for this long instead of a number of actions.')
    parser.add_argument('--seed', type=int, default=None,
                        help='Seed for the random part, printed so a run can be replayed.')
    weekly = ('service-', 'ui-')
    nightly = [s for s in SECTIONS if not s.startswith(weekly)]
    parser.add_argument('--sections', default=','.join(nightly),
                        help='Sweep sections to run; "services" and "ui" stand for all service-* and ui-* '
                             'ones (default: all but those, which run weekly): %s' % ', '.join(SECTIONS))
    parser.add_argument('--no-sweep', action='store_true', help='Skip the corpus sweep.')
    parser.add_argument('--no-random', action='store_true', help='Skip the random part.')
    parser.add_argument('--results', default=None,
                        help='Directory for results and child logs (default: a new temp dir).')
    parser.add_argument('--log', default=None, help='Action log of the random part.')
    parser.add_argument('--debugger', choices=sorted(DEBUGGERS),
                        help='Run each child under this debugger, for native crash backtraces.')
    parser.add_argument('--random-child', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--case-timeout', type=int, default=CASE_TIMEOUT, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.random_child:
        random_child(args)
        return 0

    args.seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**32)
    outdir = os.path.abspath(args.results or tempfile.mkdtemp(prefix='virtaal-fuzz-'))
    os.makedirs(outdir, exist_ok=True)
    args.log = os.path.abspath(args.log or os.path.join(outdir, 'random-actions.log'))
    platform = results.current_platform()
    print('seed=%d results=%s platform=%s' % (args.seed, outdir, platform))
    faulthandler.enable()

    root = tempfile.mkdtemp(prefix='virtaal-fuzz-home-')
    found = []
    try:
        # A fresh config per section, so one section's leftovers can't
        # change what the next one sees.
        if not args.no_sweep:
            sections = []
            for name in filter(None, args.sections.split(',')):
                prefix = {'services': 'service-', 'ui': 'ui-'}.get(name)
                sections += [s for s in SECTIONS if s.startswith(prefix)] if prefix else [name]
            for section in sections:
                start = time.monotonic()
                env = child_env(prepare_home(os.path.join(root, section)))
                if section.startswith('ui-'):
                    env['LANGUAGE'] = section[len('ui-'):]
                cases = run_section(section, env, outdir, args.debugger, platform)
                print('sweep %s: %d cases in %.0f s' % (section, len(cases), time.monotonic() - start))
                found += cases
        if not args.no_random:
            found += run_random(args, child_env(prepare_home(os.path.join(root, 'random'))), outdir, args.debugger)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    return report(found, outdir, platform)

if __name__ == '__main__':
    sys.exit(main())
