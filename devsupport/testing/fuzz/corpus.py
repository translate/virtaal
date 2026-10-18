#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Text the fuzzers put into every input.

Each entry is (category, name, value); known_bugs.py refers to cases by
name. GTK widgets can't hold NUL or lone surrogates, so those are only
used where text reaches code without a widget (file content) - see
API_ONLY.
"""

CORPUS = [
    # blank / whitespace
    ('blank', 'empty', ''),
    ('space', 'one space', ' '),
    ('space', 'spaces only', '     '),
    ('space', 'tab', '\t'),
    ('space', 'newline only', '\n'),
    ('space', 'CRLF', 'a\r\nb'),
    ('space', 'lone CR', 'a\rb'),
    ('space', 'leading/trailing space', '  word  '),
    ('space', 'trailing newline', 'word\n'),
    ('space', 'NBSP', 'a\u00a0b'),
    ('space', 'NBSP only', '\u00a0'),
    ('space', 'ZWSP', 'a\u200bb'),
    ('space', 'ideographic space', 'a\u3000b'),
    ('space', 'line separator U+2028', 'a\u2028b'),
    ('space', 'paragraph separator U+2029', 'a\u2029b'),
    ('space', 'NEL U+0085', 'a\u0085b'),
    ('space', 'BOM', '\ufeffword'),
    # length
    ('length', '1 char', 'a'),
    ('length', '255 chars', 'a' * 255),
    ('length', '4096 chars one word', 'x' * 4096),
    ('length', '10k chars words', 'word ' * 2000),
    ('length', '100k chars', 'Lorem ipsum dolor sit amet. ' * 3600),
    ('length', '2000 lines', 'line\n' * 2000),
    # special characters
    ('special', 'printf', 'Open %s and %d files (100%)'),
    ('special', 'python named', '%(name)s %(count)d %'),
    ('special', 'percent alone', '%'),
    ('special', 'url-escape', 'a%20b%2Fc'),
    ('special', 'brace format', '{0} {name} {} {{x}}'),
    ('special', 'xml tags', '<b>bold</b> <br/> <g id="1">x</g>'),
    ('special', 'xml unbalanced', '<b>open & close </i>'),
    ('special', 'entities', '&amp; &lt; &#x41; &nbsp; &bogus;'),
    ('special', 'pango markup', '<span foreground="red">x</span>'),
    ('special', 'quotes', '"double" \'single\' `back`'),
    ('special', 'backslashes', 'C:\\path\\new\\table \\n \\'),
    ('special', 'ini syntax', '[section]\nkey = value\n; comment\n# hash'),
    ('special', 'ini value chars', 'a=b:c;d#e|f,g'),
    ('special', 'pipes and commas', 'en,af|de,fr'),
    ('special', 'path traversal', '../../../etc/passwd'),
    ('special', 'url', 'https://example.com/?q=%(query)s&x=1#frag'),
    ('special', 'shell', '$(id) `id` ; rm -rf ~ && echo'),
    ('special', 'regex meta', '.*+?()[]{}^$|\\'),
    ('special', 'regex unbalanced (', '('),
    ('special', 'regex unbalanced [', '[a-'),
    ('special', 'regex catastrophic', '(a+)+$'),
    ('special', 'regex zero-width', '^'),
    ('special', 'regex star', 'a*'),
    ('special', 'fts operators', 'Do NOT delete this NEAR the AND OR file'),
    ('special', 'fts quote star', 'word* "phrase -minus ^caret'),
    ('special', 'accelerators', '_File &Edit ~Tools'),
    ('special', 'sql', "'; DROP TABLE sources; --"),
    ('special', 'email-ish', 'Name <a@b.c>, Other <x@y>'),
    ('special', 'header injection', 'Me\nPlural-Forms: nplurals=9; plural=0;'),
    # unicode
    ('unicode', 'latin accents', 'Ünïcödé ñ ç ß'),
    ('unicode', 'NFD combining', 'e\u0301 a\u0308 n\u0303'),
    ('unicode', 'stacked combining', 'a' + '\u0301' * 50),
    ('unicode', 'CJK', '中文字 日本語 한국어'),
    ('unicode', 'Arabic RTL', 'مرحبا بالعالم'),
    ('unicode', 'Hebrew RTL + digits', 'שלום 123 עולם'),
    ('unicode', 'bidi override', 'abc\u202edef\u202c'),
    ('unicode', 'bidi isolates', '\u2067abc\u2069 \u200f\u200e'),
    ('unicode', 'Devanagari', 'नमस्ते क्षत्रिय'),
    ('unicode', 'Thai', 'สวัสดีครับ'),
    ('unicode', 'emoji', '👍🏽 🇿🇦 ❤️'),
    ('unicode', 'ZWJ emoji', '👨\u200d👩\u200d👧\u200d👦'),
    ('unicode', 'astral math', '𝔘𝔫𝔦𝔠𝔬𝔡𝔢 𝟙𝟚𝟛'),
    ('unicode', 'private use', '\ue000\uf8ff'),
    ('unicode', 'noncharacters', '\ufdd0\ufffe\uffff'),
    ('unicode', 'replacement char', '\ufffd'),
    ('unicode', 'zalgo', 'Z̴̧̛͓̝a̸̛̖͎l̷̢̛g̵̨̛o̶̧̕'),
    ('unicode', 'turkish dotless', 'İı ǅ ﬁ ß'),
    ('control', 'C0 controls', 'a\x01b\x07c\x1bd'),
    ('control', 'vertical tab / form feed', 'a\x0bb\x0cc'),
    ('control', 'DEL', 'a\x7fb'),
    ('control', 'C1 controls', 'a\x80b\x9fc'),
]

# Never reach a GTK widget unchanged: GTK's C strings stop at NUL and its
# UTF-8 can't hold lone surrogates.
API_ONLY = [
    ('control', 'NUL', 'a\x00b'),
    ('unicode', 'lone surrogate', 'a\ud800b'),
]


def short(value, n=40):
    """repr() cut to n characters, safe for any console encoding."""
    r = ascii(value)
    return r if len(r) <= n else r[:n] + '...(%d chars)' % len(value)
