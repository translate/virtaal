#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from translate.filters.checks import CheckerConfig, KdeChecker
from translate.storage import ts2

from virtaal.support.qtchecks import QtChecker


def _unit(source, target):
    unit = ts2.tsunit(source)
    unit.target = target
    return unit


def test_ampersand_is_the_accelerator():
    checker = QtChecker()

    assert 'accelerators' in checker.run_filters(_unit('&File', 'Lêer'))
    assert 'accelerators' not in checker.run_filters(_unit('&File', '&Lêer'))


def test_numbered_placeholders_are_variables():
    assert 'variables' in QtChecker().run_filters(_unit('%1 files', 'lêers'))


def test_kde_translator_credits_are_not_checked():
    # KDE adds its own credit messages on top of Qt
    unit = _unit('Your names', 'Jan Smit')

    assert 'credits' in KdeChecker().run_filters(unit)
    assert 'credits' not in QtChecker().run_filters(unit)


def test_a_given_checker_config_is_kept():
    checker = QtChecker(checkerconfig=CheckerConfig(targetlanguage='af'))

    assert checker.config.targetlanguage == 'af'
    assert checker.config.accelmarkers == ['&']
