#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from .defaultmode import DefaultMode
from .qualitycheckmode import QualityCheckMode
from .quicktransmode import QuickTranslateMode
from .searchmode import SearchMode
from .workflowmode import WorkflowMode

modeclasses = [DefaultMode, QuickTranslateMode, SearchMode, QualityCheckMode, WorkflowMode]

__all__ = ['modeclasses']
