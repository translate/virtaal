#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Parse a Hunspell/MyThes thesaurus .dat file (hunspell/mythes) into
an in-memory {word: [(part_of_speech, [synonyms]), ...]} lookup.

Deliberately ignores the accompanying .idx file - it's only an
optimisation for random-access reads of a .dat too big to load
whole, and real repo folders don't reliably ship one (LibreOffice's
own pl_PL, for one, has no .idx alongside its real .dat). These
thesauruses are a few MB at most - loading the whole file once and
keying a dict by word is simpler, and just as fast for a single
look-up, as maintaining the .idx's byte-offset index would be.

Format (matches LibreOffice's own pl_PL/th_pl_PL_v2.dat, not just
mythes' own README's higher-level description):

    UTF-8
    word|meaning_count
    pos|synonym1|synonym2|...
    pos|synonym1|synonym2|...
    ...

repeated per word. `pos` is a part-of-speech tag when the source data
provides one, else a literal '-' placeholder (as pl_PL's does,
throughout)."""


def parse_thesaurus(dat_bytes):
    """Parse .dat bytes into {word: [(pos, [synonyms]), ...]}. Pure
    function, no I/O. The first line (a charset declaration) is
    trusted for decoding; falls back to UTF-8 if that charset isn't
    recognised."""
    newline = dat_bytes.index(b'\n')
    charset = dat_bytes[:newline].decode('ascii', errors='replace').strip()
    try:
        text = dat_bytes[newline + 1:].decode(charset)
    except LookupError:
        text = dat_bytes[newline + 1:].decode('utf-8')

    lines = text.split('\n')
    result = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if '|' not in line:
            i += 1
            continue
        word, _, count_str = line.rpartition('|')
        try:
            count = int(count_str)
        except ValueError:
            i += 1
            continue
        meanings = []
        for meaning_line in lines[i + 1:i + 1 + count]:
            pos, *synonyms = meaning_line.split('|')
            meanings.append((pos, synonyms))
        result[word] = meanings
        i += 1 + count
    return result


def lookup(thesaurus, word):
    """The meanings for word, trying an exact match first then a
    lower-cased one - MyThes keeps a headword's original case (e.g.
    "ABC"), but most look-ups won't match that exactly. None if
    nothing matches either way."""
    if word in thesaurus:
        return thesaurus[word]
    return thesaurus.get(word.lower())
