#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from .basetmmodel import unescape_html_entities


def test_unescape_html_entities():
    """Test the unescaping of &amp; and &#39; type HTML escapes"""
    assert unescape_html_entities("This &amp; That") == "This & That"
    assert unescape_html_entities("&#39;n Vertaler") == "'n Vertaler"
    assert unescape_html_entities("Copyright &copy; 2009 Virtaa&#7741;") == "Copyright © 2009 Virtaaḽ"
