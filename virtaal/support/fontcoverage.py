#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Find the characters of each shipped interface language that the
fonts Virtaal sets up can't display (#4421) - for checking a packaged
build, whose fonts and font fallback differ by platform:

    virtaal --run-module virtaal.support.fontcoverage [<output file>]

Renders every message of every catalog each language ships, and the
language's own name as Preferences lists it, with the UI font and the
editor font. Prints one line per language, font and missing character,
then "new: N", the number not in KNOWN_GAPS.
"""

import gettext
import os
import unicodedata

# A package's share/locale/<code>/LC_MESSAGES/, or a dev checkout's mo/<code>/.
CATALOG_DIRS = (('LC_MESSAGES',), ())
SKIPPED = ('pseudo', 'pseudo-bidi', 'pseudo-source', 'pseudo-priority')



def span(first, last):
    """Every character from first to last, e.g. a script's block."""
    return ''.join(map(chr, range(ord(first), ord(last) + 1)))


# Gaps with an open issue: (issue, platform, font, characters, languages),
# languages being the interface languages it happens in, or ALL.
# A new gap fails the check; one that no longer happens is only reported,
# since the platform's fonts can change under us.
ALL = None
KNOWN_GAPS = [
    (4465, 'macos', 'ui', '华汉语', ['ja']),
    (4465, 'macos', 'ui', '∶', ALL),  # RATIO, on macOS 15
]


def _catalog_dir(localedir, code):
    for sub in CATALOG_DIRS:
        path = os.path.join(localedir, code, *sub)
        if os.path.isfile(os.path.join(path, 'virtaal.mo')):
            return path
    return None


def shipped_languages(localedir):
    """Codes with a Virtaal catalog in localedir, mapped to the folder
        holding their catalogs."""
    try:
        codes = sorted(os.listdir(localedir))
    except OSError:
        return {}
    found = {}
    for code in codes:
        if code in SKIPPED:
            continue
        path = _catalog_dir(localedir, code)
        if path:
            found[code] = path
    return found


def messages(path):
    """The translations in every catalog in path."""
    texts = set()
    for name in sorted(os.listdir(path)):
        if not name.endswith('.mo'):
            continue
        with open(os.path.join(path, name), 'rb') as f:
            catalog = gettext.GNUTranslations(f)._catalog
        for key, value in catalog.items():
            if key and value:  # not the header
                texts.add(value)
    return texts


def fonts():
    """The UI and editor fonts as Virtaal sets them up, by name."""
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Pango

    from virtaal.common import pan_app
    from virtaal.views import rendering

    ui = Gtk.Settings.get_default().get_property('gtk-font-name') or 'Sans 10'
    return {
        'ui': Pango.FontDescription.from_string(rendering.with_font_fallbacks(ui)),
        'editor': Pango.FontDescription.from_string(rendering.with_font_fallbacks(pan_app.get_default_font())),
    }


class Renderer:
    def __init__(self, font, language):
        import gi
        gi.require_version('Gdk', '3.0')
        from gi.repository import Gdk, Pango
        # The font map GTK's own widgets use.
        context = Gdk.pango_context_get()
        context.set_language(Pango.Language.from_string(language))
        self.layout = Pango.Layout.new(context)
        self.layout.set_font_description(font)

    def unknown(self, text):
        self.layout.set_text(text, -1)
        return self.layout.get_unknown_glyphs_count()

    def missing(self, text):
        """The characters of text with no glyph: the ones whose removal
            lowers the count, so combining marks are tried in context.
            Control characters aren't a font's to display (GLib's Thai
            command-line help has an escape character)."""
        count = self.unknown(text)
        if not count:
            return set()
        return {char for char in set(text) if not char.isspace() and unicodedata.category(char) != 'Cc'
                and self.unknown(text.replace(char, '')) < count}


def check(localedir, font_descs, endonym=None):
    """{(font name, missing character): interface languages it's missing in}."""
    languages = shipped_languages(localedir)
    names = {code: endonym(code) for code in languages} if endonym else {}
    report = {}
    for code, path in languages.items():
        texts = messages(path)
        # Preferences lists every language by its own name, in every language.
        texts.update(name for name in names.values() if name)
        for font_name, font in font_descs.items():
            # The language picks the fallback fonts, so render in each.
            renderer = Renderer(font, code)
            for text in texts:
                for char in renderer.missing(text):
                    report.setdefault((font_name, char), set()).add(code)
    return report


def current_platform():
    from virtaal.common.platform import platform
    if platform.is_mac:
        return 'macos'
    if platform.is_windows:
        return 'windows'
    return 'linux'


def format_report(report, font_descs, platform_name, known=KNOWN_GAPS):
    """The report's text, and how many missing characters have no issue."""
    known = [gap for gap in known if gap[1] == platform_name]
    seen = set()
    # (font, languages, issue or None): characters, so one gap is one line.
    groups = {}
    for (font_name, char), codes in report.items():
        codes = set(codes)
        for index, (issue, _, gap_font, chars, gap_codes) in enumerate(known):
            if gap_font == font_name and char in chars:
                covered = codes if gap_codes is ALL else codes & set(gap_codes)
                if covered:
                    seen.add((index, char))
                    groups.setdefault((font_name, tuple(sorted(covered)), issue), []).append(char)
                    codes -= covered
        if codes:
            groups.setdefault((font_name, tuple(sorted(codes)), None), []).append(char)
    lines = ['font %s: %s' % (name, font.to_string()) for name, font in font_descs.items()]
    new = 0
    for (font_name, codes, issue), chars in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
        if issue is None:
            new += len(chars)
        lines.append('%s font, %s: %s: %s' % (font_name, ' '.join(codes), 'known, #%d' % issue if issue else 'NEW',
                                              ' '.join(_describe(char) for char in sorted(chars))))
    for index, (issue, _, gap_font, chars, _) in enumerate(known):
        if not any(seen_index == index for seen_index, _ in seen):
            shown = ' '.join(_describe(char) for char in chars[:3]) + (' ...' if len(chars) > 3 else '')
            lines.append('%s font: #%d displays now: %s; if it is fixed, remove it from KNOWN_GAPS'
                         % (gap_font, issue, shown))
    lines.append('new: %d' % new)
    return '\n'.join(lines) + '\n', new


def _describe(char):
    return '%s (U+%04X %s)' % (char, ord(char), unicodedata.name(char, '?'))


def main(argv):
    from virtaal.common import pan_app
    from virtaal.common.platform import platform

    font_descs = fonts()
    # A dev checkout's mo/, compiled by setup.py, else the package's own.
    localedir = os.path.join(pan_app._repo_root(), 'mo')
    if not shipped_languages(localedir):
        localedir = platform.locale_dir
    report = check(localedir, font_descs, pan_app.get_language_endonym)
    result, _ = format_report(report, font_descs, current_platform())
    if len(argv) > 1:
        with open(argv[1], 'w', encoding='utf-8') as f:
            f.write(result)
    else:
        import sys
        sys.stdout.write(result)


if __name__ == '__main__':
    import sys
    main(sys.argv)
