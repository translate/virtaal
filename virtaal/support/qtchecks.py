#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Checks specific to Qt, which translate-toolkit doesn't have yet.

KDE builds on Qt: translate-toolkit's KdeChecker is this config plus KDE's
translator credits.
"""

from translate.filters.checks import CheckerConfig, StandardChecker

qtconfig = CheckerConfig(
    accelmarkers=["&"],
    varmatches=[("%", 1)],
)


class QtChecker(StandardChecker):
    def __init__(self, **kwargs):
        checkerconfig = kwargs.get("checkerconfig")
        if checkerconfig is None:
            checkerconfig = CheckerConfig()
            kwargs["checkerconfig"] = checkerconfig
        checkerconfig.update(qtconfig)
        super().__init__(**kwargs)
