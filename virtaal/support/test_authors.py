#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.support.authors import find_authors_md, parse_contributors


def test_find_authors_md_locates_the_real_repo_root_file():
    path = find_authors_md()
    assert path is not None
    assert path.endswith('AUTHORS.md')


def test_parse_contributors_reads_the_real_file():
    contributors = parse_contributors(find_authors_md())
    assert 'Friedel Wolff' in contributors
    assert 'Dwayne Bailey' in contributors


def test_parse_contributors_sections(tmp_path):
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

    contributors = parse_contributors(str(md))

    # Donors and funders isn't parsed here - see AboutDialog for why.
    assert contributors == ['Alice', 'Bob']
