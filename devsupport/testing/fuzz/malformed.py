#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Malformed and unusual translation files for the files sweep.

file_cases() gives (sweep, case, extension, content, must_open): content
is bytes, or None for a directory with that name. A file that must open
is valid enough that refusing it is a bug; any other may be refused, as
long as that is done cleanly.
"""

import os
import random

TESTFILES = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'testfiles'))

PO = '''msgid ""
msgstr ""
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Language: af\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

msgid "Open the file"
msgstr ""

msgid "Save the file"
msgstr "Stoor die lêer"

msgid "%d file"
msgid_plural "%d files"
msgstr[0] "%d lêer"
msgstr[1] "%d lêers"
'''.encode()

XLIFF = '''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
<file original="t" source-language="en" target-language="af" datatype="plaintext"><body>
<trans-unit id="1" xml:space="preserve"><source>Open the file</source></trans-unit>
<trans-unit id="2" xml:space="preserve"><source>Save the file</source><target>Stoor die lêer</target></trans-unit>
</body></file></xliff>
'''.encode()

FORMATS = ('po', 'xlf', 'ts', 'tbx', 'tmx', 'ftl', 'sdlxliff', 'mo', 'qm')
# Formats read from text; the others are binary.
TEXT_FORMATS = FORMATS[:7]
# Virtaal can't write these.
READ_ONLY_FORMATS = ('qm',)
FILE_SWEEPS = tuple('file-' + ext for ext in FORMATS) + ('file-mismatch',)


def _read(name):
    with open(os.path.join(TESTFILES, name), 'rb') as f:
        data = f.read()
    # A Windows checkout can have CRLF; the variants start from LF.
    return data if name.endswith(('.mo', '.qm')) else data.replace(b'\r\n', b'\n')


def bases():
    return {
        'po': PO,
        'xlf': XLIFF,
        'ts': _read('workflow.ts'),
        'tbx': _read('workflow.tbx'),
        'tmx': _read('workflow.tmx'),
        'ftl': _read('workflow.ftl'),
        'sdlxliff': _read('workflow.sdlxliff'),
        'mo': _read('workflow.mo'),
        'qm': _read('workflow.qm'),
    }


def _generic(ext, data, rng):
    text = ext in TEXT_FORMATS
    mid = data.find(b'\n', len(data) // 2)
    return [
        ('empty', b'', False),
        ('whitespace only', b'  \n\n\t\n', False),
        ('random binary', bytes(rng.randrange(256) for _ in range(4096)), False),
        ('truncated 50%', data[:len(data) // 2], False),
        ('truncated 90%', data[:len(data) * 9 // 10], False),
        ('invalid UTF-8', data[:mid] + b'\xff\xfe\xc3(' + data[mid:], False),
        ('NUL byte', data[:mid] + b'\x00' + data[mid:], False),
        ('UTF-8 BOM', b'\xef\xbb\xbf' + data, text),
        ('UTF-16 with BOM', data.decode('utf-8', 'replace').encode('utf-16'), False),
        ('CRLF', data.replace(b'\n', b'\r\n'), text),
        # Fluent allows only LF and CRLF.
        ('lone CR', data.replace(b'\n', b'\r'), text and ext != 'ftl'),
        ('Latin-1 bytes', data.decode('utf-8', 'replace').encode('latin-1', 'replace'), False),
        ('doubled content', data + b'\n' + data, False),
    ]


def _po_header(charset, body):
    return ('msgid ""\nmsgstr ""\n"MIME-Version: 1.0\\n"\n"Content-Type: text/plain; charset=%s\\n"\n'
            '"Content-Transfer-Encoding: 8bit\\n"\n\n%s' % (charset, body))


def _po_cases():
    po = PO
    yield 'header only', po[:po.index(b'msgid "Open')], False
    yield 'duplicate msgid', po + b'\nmsgid "Save the file"\nmsgstr "Dup"\n', True
    yield 'msgstr[5] with nplurals=2', po + b'\nmsgid "x"\nmsgid_plural "xs"\nmsgstr[0] "a"\nmsgstr[5] "b"\n', True
    yield 'nplurals=0', po.replace(b'nplurals=2', b'nplurals=0'), True
    yield 'nplurals=abc', po.replace(b'nplurals=2', b'nplurals=abc'), False
    yield 'nplurals=1000', po.replace(b'nplurals=2', b'nplurals=1000'), True
    yield 'broken plural expression', po.replace(b'plural=(n != 1)', b'plural=(n ! 1'), True
    yield 'Python code as plural', po.replace(b'plural=(n != 1)', b'plural=__import__("os").getpid()'), True
    yield 'unterminated quote', po.replace(b'msgid "Save the file"', b'msgid "Save the file'), False
    yield 'missing msgstr', po.replace(b'msgstr "Stoor die l\xc3\xaaer"\n', b''), False
    yield 'unknown charset', po.replace(b'charset=UTF-8', b'charset=bogus-9'), False
    yield 'UTF-8 labelled ISO-8859-1', po.replace(b'charset=UTF-8', b'charset=ISO-8859-1'), False
    # A UTF-8 file whose header names a charset PO can't use.
    yield 'UTF-8 labelled UTF-16', po.replace(b'charset=UTF-8', b'charset=UTF-16'), True
    yield 'ISO-8859-1', _po_header('ISO-8859-1', 'msgid "Save the file"\nmsgstr "Stoor die lêer"\n').encode(
        'latin-1'), True
    yield 'KOI8-R', _po_header('KOI8-R', 'msgid "Save"\nmsgstr "Сохранить"\n').encode(
        'koi8-r'), True
    yield 'obsolete only', _po_header('UTF-8', '#~ msgid "a"\n#~ msgstr "b"\n').encode(), False
    yield 'msgctxt only', b'msgctxt "c"\n', False
    yield 'bad escape', po.replace(b'msgid "Save the file"', b'msgid "Save \\q the \\x file \\"'), False
    yield 'previous msgid only', b'#, fuzzy\n#| msgid "old"\n', False
    yield 'invalid Language', po.replace(b'Language: af', b'Language: ,|zz@@'), True
    yield '100,000 units', po + b''.join(b'msgid "u%d"\nmsgstr ""\n\n' % i for i in range(100000)), True


def _xliff_cases():
    x = XLIFF
    body = x.split(b'?>', 1)[1]
    entities =(b'<!DOCTYPE x [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
                b'<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;"><!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;">]>')
    yield 'unclosed tag', x.replace(b'</body>', b''), False
    yield 'undeclared entity', x.replace(b'Open the file', b'Open &bogus; file'), False
    yield 'no body', (b'<?xml version="1.0"?><xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">'
                      b'<file original="t" source-language="en" datatype="plaintext"></file></xliff>'), False
    yield 'no namespace', x.replace(b' xmlns="urn:oasis:names:tc:xliff:document:1.2"', b''), True
    yield 'XLIFF 2.0', x.replace(b'version="1.2"', b'version="2.0"').replace(b'document:1.2', b'document:2.0'), False
    yield 'duplicate ids', x.replace(b'id="2"', b'id="1"'), True
    yield 'no id', x.replace(b' id="1"', b''), True
    yield 'unbalanced inline markup', x.replace(b'<target>Stoor die l\xc3\xaaer</target>',
                                                b'<target><g id="1">Stoor</target>'), False
    yield 'inline markup 200 deep', x.replace(b'Open the file', b'<g id="a">' * 200 + b'x' + b'</g>' * 200), True
    yield 'bpt without ept', x.replace(b'Open the file', b'<bpt id="1">&lt;b&gt;</bpt>Open'), True
    yield 'two file elements', x.replace(b'</file>', b'</file><file original="u" source-language="en" '
                                         b'target-language="de" datatype="plaintext"><body><trans-unit id="9">'
                                         b'<source>x</source></trans-unit></body></file>'), True
    yield 'invalid target-language', x.replace(b'target-language="af"', b'target-language=",|zz@@"'), True
    yield 'internal entity', (b'<?xml version="1.0"?><!DOCTYPE xliff [<!ENTITY prod "Virtaal">]>'
                              + body.replace(b'Open the file', b'Open &prod; now')), False
    yield 'external entity', (b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
                              + body.replace(b'Open the file', b'&e;')), False
    yield 'entity expansion', b'<?xml version="1.0"?>' + entities + body.replace(b'Open the file', b'&d;'), False
    yield 'unknown state', x.replace(b'<target>', b'<target state="bogus-state">'), True
    yield 'approved=maybe', x.replace(b'<trans-unit id="2"', b'<trans-unit id="2" approved="maybe"'), True


def file_cases():
    rng = random.Random(4388)
    data = bases()
    cases = []
    for ext, content in data.items():
        sweep = 'file-' + ext
        for name, blob, must_open in _generic(ext, content, rng):
            cases.append((sweep, name, ext, blob, must_open))
        specific = {'po': _po_cases, 'xlf': _xliff_cases}.get(ext)
        for name, blob, must_open in (specific() if specific else ()):
            cases.append((sweep, name, ext, blob, must_open))
    for name, ext, blob in (
            ('PO content as .xlf', 'xlf', data['po']),
            ('XLIFF content as .po', 'po', data['xlf']),
            ('TS content as .xlf', 'xlf', data['ts']),
            ('PO content as .ts', 'ts', data['po']),
            ('PNG as .po', 'po', b'\x89PNG\r\n\x1a\n' + bytes(64)),
            ('empty zip', 'zip', b'PK\x05\x06' + bytes(18)),
            ('random bytes as .zip', 'zip', bytes(rng.randrange(256) for _ in range(512))),
            ('PO without extension', '', data['po'])):
        cases.append(('file-mismatch', name, ext, blob, False))
    cases.append(('file-mismatch', 'directory named .po', 'po', None, False))
    return cases
