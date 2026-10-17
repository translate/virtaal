#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import json
import sys
import types

import fuzz_ui
import record


def _events(path, *events):
    with open(path, 'w', encoding='utf-8') as f:
        for event in events:
            f.write(json.dumps(event) + '\n')
    return str(path)


def _marker(**event):
    return record.STDERR_MARKER + json.dumps(event)


def test_glib_criticals_on_stderr_go_to_the_running_case(tmp_path):
    path = _events(tmp_path / 'r.jsonl',
                   {'event': 'begin', 'sweep': 'source', 'case': 'a'}, {'event': 'end', 'elapsed': 0.1},
                   {'event': 'begin', 'sweep': 'source', 'case': 'b'}, {'event': 'end', 'elapsed': 0.1},
                   {'event': 'done'})
    stderr = '\n'.join([
        _marker(event='begin', sweep='source', case='a'), _marker(event='end'),
        _marker(event='begin', sweep='source', case='b'),
        "(sweep.py:12): Pango-CRITICAL **: 13:47:35.778: pango_layout_get_cursor_pos: assertion 'x' failed",
        _marker(event='end'), _marker(event='done'),
    ])
    cases, finished, _ = fuzz_ui.parse_child(path, stderr)
    assert finished
    assert cases[0]['problems'] == []
    assert cases[1]['problems'][0]['kind'] == 'critical'
    assert cases[1]['problems'][0]['signature'] == "Pango: pango_layout_get_cursor_pos: assertion 'x' failed"


def test_glib_warning_between_cases_is_outside_a_case(tmp_path):
    path = _events(tmp_path / 'r.jsonl', {'event': 'begin', 'sweep': 's', 'case': 'a'}, {'event': 'end', 'elapsed': 0})
    cases, finished, _ = fuzz_ui.parse_child(path, '(x:1): Gtk-WARNING **: 10:00:00.000: odd\n')
    assert not finished
    assert cases[-1]['case'] == record.OUTSIDE_CASE
    assert cases[-1]['problems'][0]['kind'] == 'glib-warning'


def test_a_case_without_an_end_is_unfinished(tmp_path):
    path = _events(tmp_path / 'r.jsonl', {'event': 'begin', 'sweep': 's', 'case': 'a'})
    cases, finished, _ = fuzz_ui.parse_child(path, '')
    assert cases[0]['elapsed'] is None and not finished


def test_died_in_tells_a_timeout_from_a_crash():
    begun = _marker(event='begin', sweep='s', case='a')
    assert fuzz_ui.died_in([], begun + '\nTimeout (0:01:00)!\nThread 0x1')['kind'] == 'timeout'
    assert fuzz_ui.died_in([], begun + '\nFatal Python error: Segmentation fault')['kind'] == 'crash'
    # A timeout dump from an earlier, finished case doesn't count.
    assert fuzz_ui.died_in([], 'Timeout (0:01:00)!\n' + begun + '\nSegfault')['kind'] == 'crash'


def _traceback_through(filename):
    code = compile('def translate_unit():\n    raise ValueError("x")\n', filename, 'exec')
    namespace = {}
    exec(code, namespace)
    try:
        namespace['translate_unit']()
    except ValueError:
        return sys.exc_info()


def test_signature_names_the_innermost_virtaal_function():
    exc_type, _, tb = _traceback_through('/src/virtaal/support/tmdb.py')
    assert record.exception_signature(exc_type, tb) == 'ValueError translate_unit'


def test_signature_skips_harness_frames_but_not_virtaal_reached_through_them():
    exc_type, _, tb = _traceback_through('/src/devsupport/testing/fuzz/../../../virtaal/support/tmdb.py')
    assert record.exception_signature(exc_type, tb) == 'ValueError translate_unit'
    exc_type, _, tb = _traceback_through('/src/devsupport/testing/fuzz/sweep.py')
    assert record.exception_signature(exc_type, tb) == 'ValueError '


def test_offline_environment(tmp_path):
    env = fuzz_ui.child_env(str(tmp_path))
    assert env['HOME'] == str(tmp_path)
    assert env['https_proxy'].startswith('http://127.0.0.1')
    assert '127.0.0.1' in env['no_proxy']


def test_prepared_config_turns_off_network_plugins(tmp_path, monkeypatch):
    monkeypatch.setattr(fuzz_ui, 'sys', types.SimpleNamespace(platform='linux'))
    home = fuzz_ui.prepare_home(str(tmp_path))
    plugins = open(fuzz_ui.config_dir(home) + '/plugins.ini', encoding='utf-8').read()
    assert 'amagama' in plugins and 'thesaurus' in plugins and 'pontoon' in plugins
