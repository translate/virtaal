#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import os

from virtaal.support import authors
from virtaal.support.authors import find_authors_md, parse_contributors


def test_find_authors_md_locates_the_real_repo_root_file():
    path = find_authors_md()
    assert path is not None
    assert path.endswith('AUTHORS.md')


def test_find_authors_md_falls_back_to_share_virtaal(tmp_path, monkeypatch):
    """A real install that isn't PyInstaller-frozen (Flatpak, or a
        plain pip install) has no checkout-relative repo root at all -
        find_authors_md() needs to fall through to
        pan_app.get_abs_data_filename()'s share/ resolution, which
        share/virtaal/AUTHORS.md (a symlink to the real file) is set
        up to satisfy."""
    # Simulate "not a checkout" by pointing this module's own
    # __file__ somewhere with no AUTHORS.md two directories up.
    monkeypatch.setattr(authors, '__file__', str(tmp_path / "support" / "authors.py"))

    path = find_authors_md()

    assert path is not None
    assert path.endswith(os.path.join('share', 'virtaal', 'AUTHORS.md'))
    assert 'Friedel Wolff' in parse_contributors(path)


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
