#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.models.storemodel import StoreModel


def test_load_file_with_an_empty_source_string(tmp_path):
    # translate/virtaal#3249: an empty <source></source> in a .ts file
    # parses with unit.source == None, which used to crash statsdb's
    # own "source VARCHAR NOT NULL" constraint on load.
    ts_file = tmp_path / "empty_source.ts"
    ts_file.write_text("""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS language="da">
<context>
<name>Test</name>
<message>
<source></source>
<translation>foo</translation>
</message>
</context>
</TS>
""")
    model = StoreModel(str(ts_file), None)
    assert len(model) == 1
