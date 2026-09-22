#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from virtaal.plugins.tm.tmcontroller import TMController


def _make_controller(matches=None, max_matches=5, current_query='hello', storecursor=True):
    controller = TMController.__new__(TMController)
    controller.storecursor = storecursor
    controller.current_query = current_query
    controller.matches = matches if matches is not None else []
    controller.max_matches = max_matches
    controller.displayed = []
    controller.view = SimpleNamespace(display_matches=lambda matches: controller.displayed.append(list(matches)))
    return controller


def _tmmodel(display_name='Some TM'):
    return SimpleNamespace(display_name=display_name)


def test_accept_response_ignores_a_response_after_the_file_was_closed():
    controller = _make_controller(storecursor=None)

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': 90}])

    assert controller.matches == []
    assert controller.displayed == []


def test_accept_response_ignores_a_stale_query():
    controller = _make_controller(current_query='goodbye')

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': 90}])

    assert controller.matches == []


def test_accept_response_ignores_an_empty_matches_list():
    controller = _make_controller()

    controller.accept_response(_tmmodel(), 'hello', [])

    assert controller.matches == []
    assert controller.displayed == []


def test_accept_response_coerces_a_string_quality_to_int():
    controller = _make_controller()

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': '90'}])

    assert controller.matches[0]['quality'] == 90


def test_accept_response_defaults_a_missing_tmsource_to_the_models_display_name():
    controller = _make_controller()

    controller.accept_response(_tmmodel('Amagama'), 'hello', [{'target': 'hallo', 'quality': 90}])

    assert controller.matches[0]['tmsource'] == 'Amagama'


def test_accept_response_adds_a_genuinely_new_match_and_displays_it():
    controller = _make_controller()

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': 90}])

    assert len(controller.matches) == 1
    assert controller.displayed == [controller.matches]


def test_accept_response_keeps_an_existing_qualified_match_over_a_duplicate_target():
    """A duplicate suggestion (same normalized target) that already has
        quality information is trusted over a new one - only a
        qualityless existing match (e.g. from MT) gets replaced."""
    existing = {'target': 'hallo', 'quality': 95, 'tmsource': 'Local TM', 'query_str': 'hello'}
    controller = _make_controller(matches=[existing])

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': 80}])

    assert controller.matches == [existing]
    assert controller.displayed == []  # nothing new, so display_matches is never called


def test_accept_response_replaces_an_unqualified_duplicate_with_a_qualified_one():
    existing = {'target': 'hallo', 'quality': None, 'tmsource': 'Machine Translation', 'query_str': 'hello'}
    controller = _make_controller(matches=[existing])

    controller.accept_response(_tmmodel(), 'hello', [{'target': 'hallo', 'quality': 90}])

    assert len(controller.matches) == 1
    assert controller.matches[0]['quality'] == 90
    assert existing not in controller.matches


def test_accept_response_sorts_by_quality_descending_and_truncates_to_max_matches():
    controller = _make_controller(max_matches=2)

    controller.accept_response(_tmmodel(), 'hello', [
        {'target': 'laag', 'quality': 60},
        {'target': 'hoog', 'quality': 95},
        {'target': 'middel', 'quality': 80},
    ])

    assert [m['target'] for m in controller.matches] == ['hoog', 'middel']
