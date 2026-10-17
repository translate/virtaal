#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Matches fuzz failures against known_bugs.py and reports the outcome.

A result is one case: {'sweep', 'case', 'problems': [{'kind',
'signature', 'detail'}], 'elapsed'}. A run fails on a problem that no
entry matches (new), on a strict entry whose failure didn't happen
(stale: the bug is fixed and the entry has to go), on an entry naming a
case its sweep doesn't have, and on an entry whose issue is closed.
"""

import html
import json
import sys
import urllib.request

ALL = '*'
PLATFORMS = ('linux', 'macos', 'windows')


def current_platform():
    if sys.platform.startswith('win'):
        return 'windows'
    if sys.platform == 'darwin':
        return 'macos'
    return 'linux'


def normalize(entry):
    sweeps = entry['sweep']
    return {
        'issue': entry['issue'],
        'sweeps': [sweeps] if isinstance(sweeps, str) else list(sweeps),
        'cases': entry['cases'],
        'kind': entry['kind'],
        'match': entry.get('match', ''),
        'platforms': entry.get('platforms', PLATFORMS),
        'strict': entry.get('strict', True),
    }


def _matches(entry, sweep, case, problem):
    return (sweep in entry['sweeps']
            and (entry['cases'] == ALL or case in entry['cases'])
            and problem['kind'] == entry['kind']
            and entry['match'] in problem['signature'] + '\n' + problem['detail'])


class Outcome:
    def __init__(self):
        self.cases = 0
        self.sweeps = set()
        self.new = []        # (result, problem)
        self.known = []      # (entry, result, problem)
        self.stale = []      # (entry, sweep, case) - case is ALL for a '*' entry
        self.unknown = []    # (entry, sweep, case) - no such case in that sweep
        self.closed = []     # entry

    @property
    def failed(self):
        return bool(self.new or self.stale or self.unknown or self.closed)


def classify(results, known_bugs, platform):
    entries = [e for e in map(normalize, known_bugs) if platform in e['platforms']]
    outcome = Outcome()
    ran = set()
    hits = set()
    for result in results:
        sweep, case = result['sweep'], result['case']
        outcome.cases += 1
        outcome.sweeps.add(sweep)
        ran.add((sweep, case))
        for problem in result['problems']:
            for i, entry in enumerate(entries):
                if _matches(entry, sweep, case, problem):
                    outcome.known.append((entry, result, problem))
                    hits.add((i, sweep, case))
                    hits.add((i, sweep, ALL))
                    break
            else:
                outcome.new.append((result, problem))

    for i, entry in enumerate(entries):
        if not entry['strict']:
            continue
        for sweep in entry['sweeps']:
            if sweep not in outcome.sweeps:
                continue  # not run this time, e.g. another job's sweep
            if entry['cases'] == ALL:
                if (i, sweep, ALL) not in hits:
                    outcome.stale.append((entry, sweep, ALL))
                continue
            for case in entry['cases']:
                if (sweep, case) not in ran:
                    outcome.unknown.append((entry, sweep, case))
                elif (i, sweep, case) not in hits:
                    outcome.stale.append((entry, sweep, case))
    return outcome


def check_closed(outcome, known_bugs, issue_states):
    """issue_states: {issue number: 'open' | 'closed'}; missing ones are
    skipped."""
    seen = set()
    for entry in map(normalize, known_bugs):
        if entry['issue'] in seen:
            continue
        seen.add(entry['issue'])
        if issue_states.get(entry['issue']) == 'closed':
            outcome.closed.append(entry)


def fetch_issue_states(issues, repo='translate/virtaal', token=None, timeout=10):
    """Issue states from the GitHub API, or {} when it can't be reached."""
    states = {}
    headers = {'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    for issue in sorted(set(issues)):
        url = 'https://api.github.com/repos/%s/issues/%d' % (repo, issue)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as response:
                states[issue] = json.load(response)['state']
        except Exception:
            return {}
    return states


def _cell(text, limit=120):
    text = ' '.join(str(text).split())
    if len(text) > limit:
        text = text[:limit] + '...'
    return html.escape(text).replace('|', '\\|')


def _cases(entry, sweep, case):
    return 'every case' if case == ALL else '"%s"' % _cell(case)


def summary(outcome, platform, issue_check=True):
    lines = ['## UI fuzzing: %s' % platform, '']
    lines.append('%d cases in %d sweeps. %d new failures, %d known, %d stale entries.' % (
        outcome.cases, len(outcome.sweeps), len(outcome.new), len(outcome.known), len(outcome.stale)))
    if not issue_check:
        lines.append('')
        lines.append("Couldn't reach GitHub to check whether the listed issues are still open.")
    if outcome.new:
        lines += ['', '### New failures', '',
                  'Not in known_bugs.py. File an issue and add an entry, or fix it.', '',
                  '| Sweep | Case | Kind | Signature |', '|---|---|---|---|']
        for result, problem in outcome.new:
            lines.append('| %s | %s | %s | %s |' % (_cell(result['sweep']), _cell(result['case']),
                                                   _cell(problem['kind']), _cell(problem['signature'] or problem['detail'])))
        lines += ['', '<details><summary>Details</summary>', '']
        for result, problem in outcome.new:
            lines += ['**%s / %s / %s**' % (_cell(result['sweep']), _cell(result['case']), _cell(problem['kind'])),
                      '', '<pre>%s</pre>' % html.escape(problem['detail'][-3000:]), '']
        lines.append('</details>')
    if outcome.stale:
        lines += ['', '### Stale known-bug entries', '',
                  "The listed failure didn't happen. If the issue is fixed, remove the entry so a regression is caught.", '']
        for entry, sweep, case in outcome.stale:
            lines.append('- #%d: %s, %s, %s' % (entry['issue'], sweep, _cases(entry, sweep, case), entry['kind']))
    if outcome.unknown:
        lines += ['', '### Entries naming a case the sweep doesn\'t have', '']
        for entry, sweep, case in outcome.unknown:
            lines.append('- #%d: %s, "%s"' % (entry['issue'], sweep, _cell(case)))
    if outcome.closed:
        lines += ['', '### Entries for closed issues', '', 'Remove the entry, or reopen the issue.', '']
        for entry in outcome.closed:
            lines.append('- #%d' % entry['issue'])
    if outcome.known:
        counts = {}
        for entry, result, problem in outcome.known:
            key = (entry['issue'], result['sweep'], problem['kind'])
            counts[key] = counts.get(key, 0) + 1
        lines += ['', '<details><summary>Known failures</summary>', '',
                  '| Issue | Sweep | Kind | Failures |', '|---|---|---|---|']
        for (issue, sweep, kind), n in sorted(counts.items()):
            lines.append('| #%d | %s | %s | %d |' % (issue, _cell(sweep), _cell(kind), n))
        lines += ['', '</details>']
    return '\n'.join(lines) + '\n'
