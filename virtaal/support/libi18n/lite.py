#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Lite catalogs: Virtaal's own translations of a library's messages
for languages the library doesn't fully translate (po/lite/<domain>/
<lang>.po), shipped merged into the library's own upstream catalog -
upstream's translation wins, lite only fills the messages upstream
lacks. A lite catalog alone would hide every other upstream message,
since a gettext domain is bound to one directory.

Kept free of virtaal.common imports so setup.py can use it at build
time.
"""

import os
import re
import struct

MO_MAGIC = 0x950412de

# The GI namespace whose install prefix holds each library's catalogs.
LIBRARY_NAMESPACES = {
    "gtk30": "Gtk",
    "glib20": "GLib",
    "gtkspell3": "GtkSpell",
    "gtk-mac-integration": "GtkosxApplication",
}


def library_locale_dir(namespace):
    """share/locale/ under the install prefix of a GI namespace's
    typelib, or None if it isn't installed."""
    try:
        import gi
        if namespace in ("Gtk", "GtkSpell"):
            gi.require_version("Gtk", "3.0")
            gi.require_version(namespace, "3.0")
        elif namespace == "GtkosxApplication":
            gi.require_version(namespace, "1.0")
        __import__("gi.repository." + namespace)
        from gi import _gi
        path = _gi.Repository.get_default().get_typelib_path(namespace)
    except (ImportError, ValueError):
        return None
    while path and os.path.dirname(path) != path:
        path = os.path.dirname(path)
        locale_dir = os.path.join(path, "share", "locale")
        if os.path.isdir(locale_dir):
            return locale_dir
    return None


def _charset(header):
    match = re.search(r"charset=([\w-]+)", header)
    return match.group(1) if match else "utf-8"


def read_mo(path):
    """{original: translation} from a .mo file, header (original "")
    included. Originals keep any msgctxt in front, separated by \\x04,
    and any msgid_plural after, separated by \\0. Revision 1's extra
    system-dependent strings are left out."""
    with open(path, "rb") as f:
        data = f.read()
    order = "<" if struct.unpack("<I", data[:4])[0] == MO_MAGIC else ">"
    count, originals, translations = struct.unpack(order + "III", data[8:20])
    raw = {}
    for i in range(count):
        olength, ooffset = struct.unpack(order + "II", data[originals + 8 * i:originals + 8 * i + 8])
        tlength, toffset = struct.unpack(order + "II", data[translations + 8 * i:translations + 8 * i + 8])
        raw[data[ooffset:ooffset + olength]] = data[toffset:toffset + tlength]
    charset = _charset(raw.get(b"", b"").decode("ascii", "replace"))
    return {key.decode(charset): value.decode(charset) for key, value in raw.items()}


def read_lite_po(path):
    """{original: translation} of a lite .po file's translated
    messages, header (original "") included, keyed as read_mo() keys
    them."""
    from translate.storage import pypo
    with open(path, "rb") as f:
        store = pypo.pofile(f)
    messages = {}
    for unit in store.units:
        if unit.isheader():
            messages[""] = str(unit.target)
            continue
        if not unit.istranslated():
            continue
        context = unit.getcontext()
        prefix = context + "\x04" if context else ""
        if unit.hasplural():
            messages[prefix + "\0".join(unit.source.strings)] = "\0".join(unit.target.strings)
        else:
            messages[prefix + str(unit.source)] = str(unit.target)
    return messages


def write_mo(path, messages):
    """Writes {original: translation} as a UTF-8 .mo file."""
    keys = sorted(messages)
    strings = [k.encode("utf-8") for k in keys] + [messages[k].encode("utf-8") for k in keys]
    originals_table = 7 * 4
    position = originals_table + 16 * len(keys)
    entries = []
    for string in strings:
        entries.append(struct.pack("<II", len(string), position))
        position += len(string) + 1
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(struct.pack("<7I", MO_MAGIC, 0, len(keys), originals_table,
                            originals_table + 8 * len(keys), 0, 0))
        f.write(b"".join(entries))
        f.write(b"".join(string + b"\0" for string in strings))


def mismatched_catalogs(datas, mo_files):
    """[(destination, bundled source, our source)] for each of our
    catalogs (mo_files: (source, destination dir) pairs, as a PyInstaller
    spec's datas list them) that a PyInstaller datas TOC
    ((destination, source, typecode) entries) bundles from somewhere
    else - e.g. GTK's own copy, which its PyInstaller hook collects at
    the same destination as a merged lite catalog."""
    ours = {os.path.normpath(os.path.join(dest_dir, os.path.basename(source))): source
            for source, dest_dir in mo_files}
    return [(dest, source, ours[os.path.normpath(dest)])
            for dest, source, _typecode in datas
            if os.path.normpath(dest) in ours
            and os.path.normpath(source) != os.path.normpath(ours[os.path.normpath(dest)])]


def merge(upstream_mo, lite_po, out_mo):
    """Writes out_mo: upstream_mo's messages (if it exists) with
    lite_po's translations (if it exists) filling only what upstream
    doesn't translate. Upstream's header, and so its Plural-Forms,
    wins."""
    messages = {}
    if lite_po and os.path.isfile(lite_po):
        messages = {k: v for k, v in read_lite_po(lite_po).items() if v}
    if upstream_mo and os.path.isfile(upstream_mo):
        messages.update({k: v for k, v in read_mo(upstream_mo).items() if v})
    header = messages.get("", "Content-Type: text/plain; charset=UTF-8\n")
    messages[""] = re.sub(r"charset=[\w-]+", "charset=UTF-8", header)
    write_mo(out_mo, messages)
