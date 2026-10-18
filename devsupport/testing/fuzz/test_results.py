#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import results


def _result(sweep, case, *problems):
    return {'sweep': sweep, 'case': case, 'elapsed': 0.1,
            'problems': [{'kind': k, 'signature': s, 'detail': d} for k, s, d in problems]}


ENTRY = dict(issue=1, sweep='search', kind='exception', match='ValueError find', cases=['a', 'b'])


def test_listed_failure_is_known():
    out = results.classify([_result('search', 'a', ('exception', 'ValueError find', '')),
                            _result('search', 'b', ('exception', 'ValueError find', ''))], [ENTRY], 'linux')
    assert len(out.known) == 2
    assert not out.failed


def test_unlisted_failure_is_new():
    out = results.classify([_result('search', 'a', ('exception', 'ValueError find', '')),
                            _result('search', 'b', ('exception', 'ValueError find', '')),
                            _result('search', 'c', ('exception', 'ValueError find', ''))], [ENTRY], 'linux')
    assert [(r['case'], p['kind']) for r, p in out.new] == [('c', 'exception')]
    assert out.failed


def test_other_kind_or_signature_is_new():
    out = results.classify([_result('search', 'a', ('exception', 'ValueError find', ''), ('critical', 'pango', '')),
                            _result('search', 'b', ('exception', 'TypeError find', ''))], [ENTRY], 'linux')
    assert [(r['case'], p['kind']) for r, p in out.new] == [('a', 'critical'), ('b', 'exception')]


def test_match_can_be_in_the_detail():
    entry = dict(ENTRY, match='bad escape')
    out = results.classify([_result('search', 'a', ('exception', 'ValueError find', 'error: bad escape')),
                            _result('search', 'b', ('exception', 'ValueError find', 'bad escape \\p'))], [entry], 'linux')
    assert not out.new


def test_listed_case_that_passes_is_stale():
    out = results.classify([_result('search', 'a', ('exception', 'ValueError find', '')),
                            _result('search', 'b')], [ENTRY], 'linux')
    assert [(e['issue'], s, c) for e, s, c in out.stale] == [(1, 'search', 'b')]
    assert out.failed


def test_entry_for_a_sweep_that_did_not_run_is_not_stale():
    out = results.classify([_result('target', 'a')], [ENTRY], 'linux')
    assert not out.stale and not out.unknown


def test_case_missing_from_a_sweep_that_ran_is_reported():
    out = results.classify([_result('search', 'a', ('exception', 'ValueError find', ''))], [ENTRY], 'linux')
    assert [(s, c) for e, s, c in out.unknown] == [('search', 'b')]
    assert out.failed


def test_all_cases_entry_needs_one_hit_per_sweep():
    entry = dict(issue=2, sweep=['replace', 'replace-all'], kind='undo-mismatch', cases=results.ALL)
    out = results.classify([_result('replace', 'a', ('undo-mismatch', '', '')), _result('replace', 'b'),
                            _result('replace-all', 'a')], [entry], 'linux')
    assert not out.new
    assert [(s, c) for e, s, c in out.stale] == [('replace-all', results.ALL)]


def test_entry_for_another_platform_is_ignored():
    entry = dict(ENTRY, platforms=['windows'])
    out = results.classify([_result('search', 'a', ('exception', 'ValueError find', '')), _result('search', 'b')],
                           [entry], 'linux')
    assert len(out.new) == 1
    assert not out.stale


def test_non_strict_entry_is_never_stale():
    entry = dict(issue=3, sweep='random', kind='critical', match='gtk', cases=results.ALL, strict=False)
    out = results.classify([_result('random', 'navigate')], [entry], 'linux')
    assert not out.failed


def test_closed_issue_fails():
    out = results.classify([], [ENTRY, dict(ENTRY, issue=5)], 'linux')
    results.check_closed(out, [ENTRY, dict(ENTRY, issue=5)], {1: 'open', 5: 'closed'})
    assert [e['issue'] for e in out.closed] == [5]
    assert out.failed


def test_summary_escapes_table_cells_and_lists_each_section():
    out = results.classify([_result('search', 'a|b', ('exception', 'ValueError <x>', 'line\nmore'))], [ENTRY], 'linux')
    text = results.summary(out, 'linux')
    assert 'a\\|b' in text
    assert '&lt;x&gt;' in text
    assert '### New failures' in text


def test_upstream_entry_matches_and_is_never_closed():
    entry = dict(upstream='translate-toolkit', sweep='file-xlf', kind='exception', match='TypeError', cases=['a'])
    out = results.classify([_result('file-xlf', 'a', ('exception', 'TypeError f', ''))], [entry], 'linux')
    results.check_closed(out, [entry], {})
    assert len(out.known) == 1 and not out.failed
    assert 'upstream (translate-toolkit)' in results.summary(out, 'linux')


def test_known_bug_list_is_well_formed():
    import corpus
    import known_bugs
    import malformed
    corpus_names = {name for _, name, _ in corpus.CORPUS + corpus.API_ONLY}
    file_names = {name for _, name, *_ in malformed.file_cases()}
    for entry in map(results.normalize, known_bugs.KNOWN_BUGS):
        assert entry['issue'] or entry['upstream'], entry
        assert set(entry['platforms']) <= set(results.PLATFORMS)
        assert entry['kind']
        if entry['cases'] == results.ALL:
            continue
        if all(sweep.startswith('file-') for sweep in entry['sweeps']):
            assert set(entry['cases']) <= file_names, entry
        elif not set(entry['sweeps']) & {'paths', 'saving', 'random'}:
            assert set(entry['cases']) <= corpus_names, entry
