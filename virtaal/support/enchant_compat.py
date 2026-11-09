#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Import pyenchant only if it is really there: a leftover "enchant"
directory with no __init__.py imports as an empty namespace package."""

import os
import re
import sys

_USED = ('dict_exists', 'list_languages', 'get_user_config_dir')

# What self_check() has GtkSpell check, and the words it should mark,
# by language. Hungarian's long compounds stress hunspell (#1958).
SAMPLES = {
    'en': 'This is a tset',
    'hu': 'Ez a számítógép legeslegmegszentségteleníthetetlenebbek kerékpárjavító-műhelyekben xqzwy',
}
_SPELLING_LIBRARY_RE = re.compile(r'enchant|gtkspell|hunspell|aspell|nuspell|winspell', re.IGNORECASE)


def import_enchant():
    """Return the pyenchant module, or None if it isn't usable."""
    try:
        import enchant
    except ImportError:
        return None
    if not all(hasattr(enchant, name) for name in _USED):
        return None
    return enchant


def enchant_tag(code):
    """The tag enchant finds a dictionary by for a Virtaal language code.
        Enchant matches only "language_PART" (language lowercased, the
        part uppercased) and ignores file names containing "-" or "@", so
        ca@valencia is ca_VALENCIA and sr_Latn_RS is sr_LATNRS. A
        downloaded dictionary is saved under this name (#4665)."""
    lang, _, variant = code.replace('-', '_').partition('@')
    language, _, rest = lang.partition('_')
    rest = rest.replace('_', '') + variant
    return language.lower() + ('_' + rest.upper() if rest else '')


def loaded_libraries():
    """The paths of the native libraries loaded in this process."""
    import ctypes
    if sys.platform == 'darwin':
        libsystem = ctypes.CDLL('/usr/lib/libSystem.B.dylib')
        libsystem._dyld_image_count.restype = ctypes.c_uint32
        libsystem._dyld_get_image_name.restype = ctypes.c_char_p
        libsystem._dyld_get_image_name.argtypes = [ctypes.c_uint32]
        names = (libsystem._dyld_get_image_name(i) for i in range(libsystem._dyld_image_count()))
        return [name.decode('utf-8', 'replace') for name in names if name]
    if sys.platform == 'win32':
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
        psapi.EnumProcessModules.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        ]
        modules = (wintypes.HMODULE * 4096)()
        needed = wintypes.DWORD()
        if not psapi.EnumProcessModules(kernel32.GetCurrentProcess(), modules, ctypes.sizeof(modules),
                                        ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        count = min(needed.value // ctypes.sizeof(wintypes.HMODULE), len(modules))
        buf = ctypes.create_unicode_buffer(32768)
        paths = []
        for module in modules[:count]:
            if kernel32.GetModuleFileNameW(module, buf, len(buf)):
                paths.append(buf.value)
        return paths
    with open('/proc/self/maps', encoding='utf-8', errors='replace') as maps:
        return mapped_libraries(maps)


def mapped_libraries(maps):
    """The shared libraries in /proc/<pid>/maps lines."""
    fields = (line.split(None, 5) for line in maps)
    paths = {f[5].strip() for f in fields if len(f) == 6 and f[5].startswith('/')}
    return sorted(p for p in paths if re.search(r'\.so(\.[0-9]+)*$', p))


def bundle_roots():
    """The directories this build's own libraries are in, or None when
        it isn't a bundle (a run from source)."""
    if getattr(sys, 'frozen', False):
        bundle = sys._MEIPASS
        # A macOS .app's libraries are in Contents/Frameworks and
        # Contents/Resources.
        return [os.path.dirname(bundle) if sys.platform == 'darwin' else bundle]
    if 'FLATPAK_ID' in os.environ:
        return ['/app', '/usr']
    return None


def system_dirs(platform=sys.platform, environ=os.environ):
    """Where the OS's own libraries are."""
    if platform == 'darwin':
        return ['/usr/lib', '/System']
    if platform == 'win32':
        return [environ.get('SystemRoot', r'C:\Windows')]
    return ['/lib', '/lib64', '/usr/lib', '/usr/lib64']


def _name(path):
    return re.split(r'[\\/]', path)[-1]


def _within(path, dirs, platform):
    if platform == 'win32':
        path, dirs = path.lower(), [d.lower() for d in dirs]
    sep = '\\' if platform == 'win32' else '/'
    return any(path == d or path.startswith(d.rstrip(sep) + sep) for d in dirs)


def foreign_libraries(paths, roots, system, platform=sys.platform):
    """The libraries in paths loaded from neither the bundle (roots) nor
        the OS (system): another install's copy, as a build machine has.
        A spelling library is foreign unless it is the bundle's."""
    return [
        p for p in paths
        if not _within(p, roots, platform)
        and (not _within(p, system, platform) or _SPELLING_LIBRARY_RE.search(_name(p)))
    ]


def duplicate_libraries(paths, system, platform=sys.platform):
    """The libraries in paths, the OS's (system) aside, with the same
        file name as another one: two copies loaded, or one loaded twice."""
    paths = [p for p in paths if not _within(p, system, platform)]
    names = [_name(p).lower() for p in paths]
    return [p for p, name in zip(paths, names) if names.count(name) > 1]


def spelling_libraries(paths):
    return [p for p in paths if _SPELLING_LIBRARY_RE.search(_name(p))]


def sample_text(lang):
    return SAMPLES.get(lang.split('_')[0], SAMPLES['en'])


def marked_words(buffer, tag_name='gtkspell-misspelled'):
    """The runs of text in a Gtk.TextBuffer with the tag tag_name."""
    tag = buffer.get_tag_table().lookup(tag_name)
    words, current = [], ''
    it = buffer.get_start_iter()
    while tag is not None and not it.is_end():
        if it.has_tag(tag):
            current += it.get_char()
        elif current:
            words.append(current)
            current = ''
        it.forward_char()
    if current:
        words.append(current)
    return words


def _gtkspell_lines(lang):
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('GtkSpell', '3.0')
    from gi.repository import GLib, Gtk, GtkSpell
    lines = ['typelib: %s' % gi.Repository.get_default().get_typelib_path('GtkSpell')]
    view = Gtk.TextView()
    view.get_buffer().set_text(sample_text(lang))
    checker = GtkSpell.Checker()
    checker.set_language(lang)
    checker.attach(view)
    context = GLib.MainContext.default()
    while context.iteration(False):
        pass
    lines.append('gtkspell: ok')
    lines.append('marked: %s' % ' '.join(marked_words(view.get_buffer())))
    return lines


def self_check(lang):
    """Report which enchant library and providers this build uses, the
        words GtkSpell marks in lang's sample text, and any native
        library loaded from outside the bundle - for packaging smoke
        tests (virtaal --run-module virtaal.support.enchant_compat LANG
        [OUTPUT])."""
    enchant = import_enchant()
    if enchant is None:
        return 'enchant: none\n'
    from enchant import _enchant
    lines = [
        'enchant: %s' % _enchant.enchant_lib_path,
        'providers: %s' % ' '.join(sorted(p.name for p in enchant.Broker().describe())),
        'dictionary: %s' % enchant.dict_exists(lang),
    ]
    if enchant.dict_exists(lang):
        dictionary = enchant.Dict(lang)
        words = sample_text(lang).split()
        lines.append('unknown: %s' % ' '.join(w for w in words if not dictionary.check(w)))
        lines.append('suggestions: %s' % ' '.join(dictionary.suggest(words[-1])[:3]))
    try:
        lines += _gtkspell_lines(lang)
    except Exception as e:
        lines.append('gtkspell: %s' % e)
    libraries = loaded_libraries()
    roots = bundle_roots()
    if roots is None:
        lines.append('foreign: (not a bundle)')
    else:
        lines.append('foreign: %s' % ' '.join(foreign_libraries(libraries, roots, system_dirs())))
    lines.append('duplicates: %s' % ' '.join(duplicate_libraries(libraries, system_dirs())))
    lines.append('spelling libraries: %s' % ' '.join(spelling_libraries(libraries)))
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    result = self_check(sys.argv[1] if len(sys.argv) > 1 else 'en_US')
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'w', encoding='utf-8') as f:
            f.write(result)
    else:
        sys.stdout.write(result)
