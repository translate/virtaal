"""Generates synthetic gettext locales from po/virtaal.pot, for
exercising every translatable string in the UI without an actual
translation:

- pseudo: every string wrapped in brackets ("[Save]") - the classic
  pseudo-localization marker for untranslated strings and truncation.
- pseudo-bidi: every string bracketed and wrapped in Unicode RTL
  isolate marks (RIGHT-TO-LEFT ISOLATE ... POP DIRECTIONAL ISOLATE) -
  simulates a right-to-left translation's layout while keeping the
  text itself readable Latin script (an isolate only sets the base
  direction of the run it wraps, it doesn't reorder or transliterate).
  Bracketed too, since the isolate marks alone are invisible.
- fa: every string's Unicode glyphs visually flipped (podebug's own
  "flipped" style) - not a real Farsi translation, just tagged with a
  real RTL-recognised language code so launching under it (LANG=
  fa_IR.UTF-8 LANGUAGE=fa) exercises actual whole-window RTL mirroring
  (menu/toolbar/status-bar placement), which pseudo-bidi's isolate
  marks alone don't necessarily trigger. Harder to read than
  pseudo-bidi, deliberately - it's testing Pango's real bidi character
  reordering, not just that embedded bidi runs don't corrupt layout.
- pseudo-source: every string prefixed with the catalog it comes from
  ("vt:Save" for Virtaal's own, "gtk:_Open", "glib:%.1f MB",
  "spell:Ignore All", "mac:Quit %s", "iso:German" for language and
  country names), for seeing which visible strings need a lite
  translation and which never went through gettext at all. Library
  strings are taken from their own installed catalogs; one its lite
  template (po/lite/<domain>/) lacks is marked "!" ("gtk!:Open"), a
  gap in lite coverage.
- pseudo-priority: every string prefixed with its translation priority
  from po/virtaal.priorities.yaml ("1:_Open", "1~:Search", "2:Settings",
  "3:", "x:" for one translators are never asked for), and "?:" for one
  the file doesn't list - for checking the priorities by eye. Library
  strings and language names too, from the same catalogs as
  pseudo-source.

Compiled straight into the active environment's own share/locale/ by
default (so bin/virtaal's --pseudo-translation* options work with no
separate install step) - pass --localedir to write
somewhere else instead, e.g. a frozen build's own share/locale/.
"""
import argparse
import os
import struct
import sys
import tempfile

from translate.storage.placeables import StringElem
from translate.tools import podebug
from translate.tools.pocompile import convertmo

RTL_ISOLATE_START = "\u2067"  # RIGHT-TO-LEFT ISOLATE
RTL_ISOLATE_END = "\u2069"  # POP DIRECTIONAL ISOLATE


def rewrite_bidi(self, string):
    if not isinstance(string, StringElem):
        string = StringElem(string)
    return self._rewrite_prepend_append(
        string, RTL_ISOLATE_START + "[", "]" + RTL_ISOLATE_END)


# podebug.convertpo() always instantiates the module's own podebug
# class directly - attaching the method here (rather than subclassing)
# is the only way to make its own getattr(self, f"rewrite_{style}")
# dispatch find rewrite_bidi.
podebug.podebug.rewrite_bidi = rewrite_bidi

LOCALES = {
    "pseudo": "bracket",
    "pseudo-bidi": "bidi",
    "fa": "flipped",
    "pseudo-source": None,
    "pseudo-priority": None,
}

# pseudo-source's tag for Virtaal's own catalog, and for each library
# catalog its tag and where it's installed: a GI namespace whose install
# prefix holds it, or pycountry.
VIRTAAL_TAG = "vt:"
LIBRARY_SOURCES = {
    "gtk30": ("gtk:", "Gtk"),
    "glib20": ("glib:", "GLib"),
    "gtkspell3": ("spell:", "GtkSpell"),
    "gtk-mac-integration": ("mac:", "GtkosxApplication"),
    "iso639-3": ("iso:", "pycountry"),
    "iso639-5": ("iso:", "pycountry"),
    "iso3166-1": ("iso:", "pycountry"),
}

MO_MAGIC = 0x950412de
MO_HEADER = ("Content-Type: text/plain; charset=UTF-8\n"
             "Plural-Forms: nplurals=2; plural=(n != 1);\n")


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _mo_byteorder(data):
    return "<" if struct.unpack("<I", data[:4])[0] == MO_MAGIC else ">"


def read_mo_originals(path):
    """Every msgid in a .mo file except the header, as stored: any
    msgctxt in front of it, separated by \\x04, and any msgid_plural
    after it, separated by \\0."""
    with open(path, "rb") as f:
        data = f.read()
    byteorder = _mo_byteorder(data)
    count, table = struct.unpack(byteorder + "II", data[8:16])
    originals = []
    for i in range(count):
        length, offset = struct.unpack(byteorder + "II", data[table + 8 * i:table + 8 * i + 8])
        if length:
            originals.append(data[offset:offset + length].decode("utf-8"))
    return originals


def write_mo(path, messages):
    """Writes {original: translation}, originals as read_mo_originals()
    returns them, as a .mo file with a UTF-8, two-plural-form header."""
    messages = dict(messages)
    messages[""] = MO_HEADER
    keys = sorted(messages)
    strings = [k.encode("utf-8") for k in keys] + [messages[k].encode("utf-8") for k in keys]
    originals_table = 7 * 4
    position = originals_table + 16 * len(keys)
    entries = []
    for string in strings:
        entries.append(struct.pack("<II", len(string), position))
        position += len(string) + 1
    with open(path, "wb") as f:
        f.write(struct.pack("<7I", MO_MAGIC, 0, len(keys), originals_table,
                            originals_table + 8 * len(keys), 0, 0))
        f.write(b"".join(entries))
        f.write(b"".join(string + b"\0" for string in strings))


def lite_template_keys(domain):
    """Each message of po/lite/<domain>/<domain>.pot as a .mo original's
    singular part ("msgctxt\\x04msgid"), or None without a template."""
    path = os.path.join(_repo_root(), "po", "lite", domain, domain + ".pot")
    if not os.path.isfile(path):
        return None
    from translate.storage import pypo
    with open(path, "rb") as f:
        units = pypo.pofile(f).units
    return {(unit.getcontext() + "\x04" if unit.getcontext() else "") + str(unit.source.strings[0]
                                                                         if unit.hasplural() else unit.source)
            for unit in units if not unit.isheader()}


def tag_messages(originals, tag, lite=None):
    """{original: translation}, every form of every msgid prefixed with
    tag - or, given lite (lite_template_keys()), with tag marked "!"
    ("gtk!:") for a message the lite template lacks. GTK reads its
    "default:LTR" message as the text direction, so that stays
    untranslated."""
    gap_tag = tag[:-1] + "!:"
    messages = {}
    for original in originals:
        msgid = original.rpartition("\x04")[2]
        if msgid != "default:LTR":
            prefix = gap_tag if lite is not None and original.split("\0")[0] not in lite else tag
            messages[original] = "\0".join(prefix + form for form in msgid.split("\0"))
    return messages


def tag_by_level(originals, levels):
    """{original: translation}, every form of every msgid prefixed with
    its level in levels ({msgctxt\\x04msgid: level}) - "1:", "2:", ... -
    or "?:" if levels lacks it. GTK's "default:LTR" stays untranslated,
    as in tag_messages()."""
    messages = {}
    for original in originals:
        msgid = original.rpartition("\x04")[2]
        if msgid != "default:LTR":
            prefix = levels.get(original.split("\0")[0], "?") + ":"
            messages[original] = "\0".join(prefix + form for form in msgid.split("\0"))
    return messages


def read_levels(path=None):
    """{domain: {key: level}} from a priority file (default
    po/virtaal.priorities.yaml)."""
    import yaml
    path = path or os.path.join(_repo_root(), "po", "virtaal.priorities.yaml")
    with open(path, encoding="utf-8") as f:
        domains = yaml.safe_load(f)["domains"]
    return {domain: {key: level for level, keys in by_level.items() for key in keys}
            for domain, by_level in domains.items()}


def _template_originals():
    """po/virtaal.pot's messages, as read_mo_originals() gives them."""
    from translate.storage import po
    template = po.pofile.parsefile(os.path.join(_repo_root(), "po", "virtaal.pot"))
    originals = []
    for unit in template.units:
        if unit.isheader() or unit.isobsolete():
            continue
        prefix = unit.getcontext() + "\x04" if unit.getcontext() else ""
        originals.append(prefix + ("\0".join(unit.source.strings) if unit.hasplural() else str(unit.source)))
    return originals


def library_locale_dir(namespace):
    """pycountry's locale directory, or share/locale/ under the install
    prefix of a GI namespace's typelib, or None."""
    if namespace == "pycountry":
        import pycountry
        return pycountry.LOCALES_DIR
    import gi
    try:
        if namespace in ("Gtk", "GtkSpell", "GtkosxApplication"):
            gi.require_version("Gtk", "3.0")
            gi.require_version(namespace, "1.0" if namespace == "GtkosxApplication" else "3.0")
        __import__("gi.repository." + namespace)
    except (ImportError, ValueError):
        # ValueError: a namespace this platform doesn't have
        # (GtkosxApplication off macOS).
        return None
    from gi import _gi
    path = _gi.Repository.get_default().get_typelib_path(namespace)
    while path and os.path.dirname(path) != path:
        path = os.path.dirname(path)
        locale_dir = os.path.join(path, "share", "locale")
        if os.path.isdir(locale_dir):
            return locale_dir
    return None


def _mo_count(path):
    with open(path, "rb") as f:
        data = f.read(12)
    return struct.unpack(_mo_byteorder(data) + "I", data[8:12])[0]


def fullest_catalog(locale_dirs, domain):
    """The real (not pseudo) <domain>.mo with the most messages, or
    None."""
    candidates = []
    for locale_dir in filter(None, locale_dirs):
        if not os.path.isdir(locale_dir):
            continue
        for lang in os.listdir(locale_dir):
            path = os.path.join(locale_dir, lang, "LC_MESSAGES", domain + ".mo")
            if lang not in LOCALES and os.path.isfile(path):
                candidates.append(path)
    return max(candidates, key=_mo_count, default=None)


def _generate_virtaal_mo(code, mo_dir):
    potfile = os.path.join(_repo_root(), "po", "virtaal.pot")
    with tempfile.NamedTemporaryFile(suffix=".po") as tmp_po:
        with open(potfile, "rb") as infile:
            if code == "pseudo-source":
                podebug.convertpo(infile, tmp_po, None, format=VIRTAAL_TAG)
            else:
                podebug.convertpo(infile, tmp_po, None, rewritestyle=LOCALES[code])
        tmp_po.flush()

        mo_path = os.path.join(mo_dir, "virtaal.mo")
        with open(tmp_po.name, "rb") as compile_in, open(mo_path, "w") as compile_out:
            convertmo(compile_in, compile_out, None)
        return mo_path


def _generate_library_mos(mo_dir, localedir, levels=None):
    """levels: read_levels(), to tag by level instead of by catalog."""
    for domain, (tag, namespace) in LIBRARY_SOURCES.items():
        library_dir = library_locale_dir(namespace)
        # Ubuntu moves translations out to language packs.
        langpack_dir = library_dir and os.path.join(os.path.dirname(library_dir), "locale-langpack")
        source = fullest_catalog([library_dir, langpack_dir, localedir], domain)
        if source is None:
            print("No installed %s catalog found, skipping it" % domain, file=sys.stderr)
            continue
        originals = read_mo_originals(source)
        write_mo(os.path.join(mo_dir, domain + ".mo"),
                 tag_by_level(originals, levels.get(domain, {})) if levels is not None
                 else tag_messages(originals, tag, lite_template_keys(domain)))


def generate_locale(code, localedir=None, priorities=None):
    """(re)generates a single pseudo-translation locale's virtaal.mo
    from the current po/virtaal.pot - plus LIBRARY_SOURCES catalogs for
    pseudo-source and pseudo-priority - returning the virtaal.mo path
    written. priorities: the priority file pseudo-priority reads (default
    po/virtaal.priorities.yaml). Cheap enough to call on every launch -
    see bin/virtaal's --pseudo-translation* handling."""
    localedir = localedir or os.path.join(sys.prefix, "share", "locale")
    mo_dir = os.path.join(localedir, code, "LC_MESSAGES")
    os.makedirs(mo_dir, exist_ok=True)
    if code == "pseudo-priority":
        levels = read_levels(priorities)
        _generate_library_mos(mo_dir, localedir, levels)
        mo_path = os.path.join(mo_dir, "virtaal.mo")
        write_mo(mo_path, tag_by_level(_template_originals(), levels.get("virtaal", {})))
        return mo_path
    if code == "pseudo-source":
        _generate_library_mos(mo_dir, localedir)
    return _generate_virtaal_mo(code, mo_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--localedir", default=None,
                         help="Where to write share/locale-style output (default: sys.prefix/share/locale)")
    args = parser.parse_args()

    for code in LOCALES:
        print("Wrote %s" % generate_locale(code, args.localedir))


if __name__ == "__main__":
    main()
