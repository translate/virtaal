#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from virtaal.plugins.tm.models.currentfile import TMModel


class _FakeUnit:
    def __init__(self, source, alttrans=None):
        self.source = source
        self._alttrans = alttrans if alttrans is not None else []

    def getalttrans(self):
        return self._alttrans


class _FakeUnitNoAltTrans:
    """No getalttrans attribute at all - some unit types don't have it."""
    def __init__(self, source):
        self.source = source


class _FakeAlt:
    def __init__(self, source, target, xmlelement=None):
        self.source = source
        self.target = target
        if xmlelement is not None:
            self.xmlelement = xmlelement


class _FakeCandidate:
    """A pounit-shaped fake, matching what match.unit2dict() expects."""
    def __init__(self, source, target, quality_pct):
        self.source = source
        self.target = target
        self._quality_pct = quality_pct

    def getnotes(self, origin=None):
        return 'Quality: %d%%' % self._quality_pct

    def getcontext(self):
        return ''


class _FakeMatcher:
    def __init__(self, candidates):
        self._candidates = candidates

    def matches(self, query_str):
        return self._candidates


def _make_model(min_quality=50):
    model = TMModel.__new__(TMModel)
    model.controller = SimpleNamespace(min_quality=min_quality)
    return model


def test_check_alttrans_returns_empty_list_without_getalttrans():
    model = _make_model()
    unit = _FakeUnitNoAltTrans('hello world')

    assert model._check_alttrans(unit) == []


def test_check_alttrans_returns_empty_list_when_no_alternatives():
    model = _make_model()
    unit = _FakeUnit('hello world', alttrans=[])

    assert model._check_alttrans(unit) == []


def test_check_alttrans_filters_out_low_quality_matches():
    model = _make_model(min_quality=50)
    alt = _FakeAlt('completely unrelated text', 'onvverwante teks')
    unit = _FakeUnit('hello world', alttrans=[alt])

    assert model._check_alttrans(unit) == []


def test_check_alttrans_includes_high_quality_matches_with_default_tmsource():
    model = _make_model(min_quality=50)
    alt = _FakeAlt('hello world', 'hallo wêreld')
    unit = _FakeUnit('hello world', alttrans=[alt])

    results = model._check_alttrans(unit)

    assert len(results) == 1
    assert results[0]['source'] == 'hello world'
    assert results[0]['target'] == 'hallo wêreld'
    assert results[0]['tmsource'] == 'This file'
    assert results[0]['quality'] == 100.0


def test_check_alttrans_appends_a_non_lmc_origin_to_tmsource():
    model = _make_model(min_quality=50)
    xmlelement = SimpleNamespace(get=lambda key, default='': 'some-tm-name' if key == 'origin' else default)
    alt = _FakeAlt('hello world', 'hallo wêreld', xmlelement=xmlelement)
    unit = _FakeUnit('hello world', alttrans=[alt])

    results = model._check_alttrans(unit)

    assert results[0]['tmsource'] == 'This file\nsome-tm-name'


def test_check_alttrans_expands_lmc_origin_metadata():
    class _FakePI:
        def __init__(self, target, text):
            self.target = target
            self.text = text

    pis = [
        _FakePI('contact-name', 'Jane Translator'),
        _FakePI('category', 'legal'),
        _FakePI('original', '/path/to/source.odt'),
    ]
    xmlelement = SimpleNamespace(
        get=lambda key, default='': 'lmc' if key == 'origin' else default,
        xpath=lambda expr: pis,
    )
    alt = _FakeAlt('hello world', 'hallo wêreld', xmlelement=xmlelement)
    unit = _FakeUnit('hello world', alttrans=[alt])
    model = _make_model(min_quality=50)

    results = model._check_alttrans(unit)

    # os.path.splitext() only strips the extension, not the directory.
    assert results[0]['tmsource'] == 'Jane Translator\nlegal\n/path/to/source\nlmc'


def test_check_other_units_excludes_exact_100_percent_matches():
    """A 100% match against the current file is the unit's own already-
        translated self (or an exact duplicate) - showing it back as a
        TM suggestion would be redundant noise."""
    model = _make_model()
    model.matcher = _FakeMatcher([_FakeCandidate('hello world', 'hallo wêreld', 100)])

    assert model._check_other_units(_FakeUnit('hello world')) == []


def test_check_other_units_includes_non_100_percent_matches():
    model = _make_model()
    model.matcher = _FakeMatcher([_FakeCandidate('hello world', 'hallo wêreld', 85)])

    results = model._check_other_units(_FakeUnit('hello world'))

    assert len(results) == 1
    assert results[0]['quality'] == '85'
    assert results[0]['tmsource'] == 'This file'


class _FakeExtendableMatcher:
    def __init__(self, start, stop):
        self.extended_with = []
        self._start = start
        self._stop = stop

    def extendtm(self, unit):
        self.extended_with.append(unit)

    def getstartlength(self, min_similarity, text):
        return self._start

    def getstoplength(self, min_similarity, text):
        return self._stop


def test_on_unit_modified_ignores_an_unmodified_unit():
    model = _make_model()
    model.matcher = _FakeExtendableMatcher(start=0, stop=100)
    model.cache = {'anything': ['cached']}

    model._on_unit_modified(None, _FakeUnit('x'), modified=False)

    assert model.matcher.extended_with == []
    assert model.cache == {'anything': ['cached']}


def test_on_unit_modified_extends_the_matcher_for_a_translated_unit():
    model = _make_model()
    model.matcher = _FakeExtendableMatcher(start=0, stop=100)
    model.cache = {}
    new_unit = SimpleNamespace(source='hello', istranslated=lambda: True)

    model._on_unit_modified(None, new_unit, modified=True)

    assert model.matcher.extended_with == [new_unit]


def test_on_unit_modified_prunes_only_cached_keys_within_the_affected_length_range():
    """A newly (re)translated unit could change TM suggestions for any
        other cached source string of a similar length - only those
        need to be invalidated, not the whole cache."""
    model = _make_model()
    model.matcher = _FakeExtendableMatcher(start=3, stop=6)
    model.cache = {
        'ab': ['too short, unaffected'],
        'abcd': ['within range, must be evicted'],
        'abcdefgh': ['too long, unaffected'],
    }
    new_unit = SimpleNamespace(source='hello', istranslated=lambda: True)

    model._on_unit_modified(None, new_unit, modified=True)

    assert set(model.cache.keys()) == {'ab', 'abcdefgh'}


def test_check_alttrans_falls_back_to_default_tmsource_if_lmc_parsing_raises():
    xmlelement = SimpleNamespace(
        get=lambda key, default='': 'lmc' if key == 'origin' else default,
        xpath=lambda expr: (_ for _ in ()).throw(RuntimeError('malformed XML')),
    )
    alt = _FakeAlt('hello world', 'hallo wêreld', xmlelement=xmlelement)
    unit = _FakeUnit('hello world', alttrans=[alt])
    model = _make_model(min_quality=50)

    results = model._check_alttrans(unit)

    # The lmc-specific enrichment failed, but the plain "\n" + origin
    # append happens unconditionally afterwards regardless.
    assert results[0]['tmsource'] == 'This file\nlmc'
