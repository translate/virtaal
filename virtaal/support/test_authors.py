#!/usr/bin/env python
#
# Copyright 2026 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

from virtaal.support.authors import find_authors_md, parse_authors_md


def test_find_authors_md_locates_the_real_repo_root_file():
    path = find_authors_md()
    assert path is not None
    assert path.endswith('AUTHORS.md')


def test_parse_authors_md_reads_the_real_file():
    contributors, donors = parse_authors_md(find_authors_md())
    assert 'Friedel Wolff' in contributors
    assert 'Dwayne Bailey' in contributors
    assert ('Mozilla Corporation', 'http://mozilla.com/') in donors


def test_parse_authors_md_sections(tmp_path):
    md = tmp_path / "AUTHORS.md"
    md.write_text(
        "# Title\n"
        "\n"
        "## Historical perspective\n"
        "\n"
        "Not a bullet section - ignored.\n"
        "\n"
        "## Donors and funders\n"
        "\n"
        "- Example Org (https://example.org/)\n"
        "\n"
        "## Contributors\n"
        "\n"
        "- Alice\n"
        "- Bob\n",
        encoding='utf-8')

    contributors, donors = parse_authors_md(str(md))

    assert contributors == ['Alice', 'Bob']
    assert donors == [('Example Org', 'https://example.org/')]
