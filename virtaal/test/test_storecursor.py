#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from test_scaffolding import TestScaffolding


class TestCursor(TestScaffolding):
    def test_move(self):
        self.store_controller.open_file(self.testfile[1])
        cursor = self.store_controller.cursor
        oldpos = cursor.pos
        cursor.move(1)
        assert cursor.pos == oldpos + 1
        cursor.move(-2)
        assert cursor.pos == len(cursor.indices) - 1

    def test_indices(self):
        cursor = self.store_controller.cursor
        cursor.pos = 0
        cursor.indices = [1, 2]
        assert cursor.pos == 0
        cursor.move(2)
        assert cursor.pos == 0
