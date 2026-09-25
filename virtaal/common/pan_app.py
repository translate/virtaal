#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.


#XXX: main imports lower down


# Before we even try to get anything done, set up stdout and stderr on our
# packaged windows build. This has to happen as early as possible, otherwise
# error messages will not be available for inspection.
import os
import re
import sys

from virtaal.__version__ import version_string

from .platform import platform


def _read_ini_recovering(parser, filename):
    """Read filename into parser, recovering from a corrupt/unreadable
    file instead of crashing - it may be a user's own hand-edited file
    they'd want back, so back it up rather than overwriting or
    discarding it silently, and leave parser empty so the caller falls
    back to its own defaults.

    Returns the backup path, or None if the file was fine (or absent)."""
    try:
        parser.read(filename, encoding='utf-8')
        return None
    except (ConfigParser.Error, UnicodeDecodeError) as e:
        for section in parser.sections():
            parser.remove_section(section)
        backup_path = filename + '.broken'
        n = 1
        while os.path.exists(backup_path):
            n += 1
            backup_path = '%s.broken.%d' % (filename, n)
        try:
            os.replace(filename, backup_path)
        except OSError:
            backup_path = None
        import logging
        logging.warning("%r is corrupt (%s) - backed up to %r and starting fresh", filename, e, backup_path)
        return backup_path


def get_config_dir():
    if platform.is_windows:
        confdir = os.path.join(os.environ['APPDATA'], 'Virtaal')
    elif platform.is_mac:
        confdir = os.path.expanduser('~/Library/Application Support/Virtaal')
    else:
        #TODO: skuif na ~/.config/virtaal en migreer
        confdir = os.path.expanduser('~/.virtaal')

    try:
        os.makedirs(confdir, exist_ok=True)
    except FileExistsError:
        import logging
        logging.warning("%r exists but is not a directory", confdir)

    return confdir

def _build_launch_marker(timestamp):
    """The separator line written to a frozen build's log at each
    launch - a single file can span several runs, so this both marks
    where one starts and identifies which build produced it."""
    return '=== launch %s | Virtaal %s ===\n' % (timestamp, version_string())

_LAUNCH_MARKER_RE = re.compile(r'^=== launch .*? \| Virtaal .* ===$', re.MULTILINE)
KEEP_LAST_N_LAUNCHES = 2

def _trim_log_to_last_launches(path, keep=KEEP_LAST_N_LAUNCHES):
    """Keep only the last `keep` launches of an existing frozen log,
    splitting on its own launch-marker line rather than a raw byte
    count - a byte cut risks starting mid-launch with nothing to
    orient from, a launch-count cut always leaves complete records."""
    try:
        with open(path, encoding='utf-8', errors='backslashreplace') as f:
            content = f.read()
    except OSError:
        return
    markers = [m.start() for m in _LAUNCH_MARKER_RE.finditer(content)]
    if len(markers) <= keep:
        return
    with open(path, 'w', encoding='utf-8', errors='backslashreplace') as f:
        f.write(content[markers[-keep]:])

def _open_frozen_log(path):
    """Open a frozen-build log file for append, trimmed to its last
    few launches first - unbounded growth was fine for an occasional
    --debug run, not as a default for every launch.

    No explicit encoding defaults to the system locale's codepage on
    Windows (e.g. cp1252), which can't represent arbitrary translated
    text - logging.debug() itself could then raise UnicodeEncodeError."""
    _trim_log_to_last_launches(path)
    return open(path, 'a', buffering=1, encoding='utf-8', errors='backslashreplace')

# Only for the packaged (frozen/PyInstaller) build - a windowed
# subsystem executable has no console, so this is the only way to get
# error messages out of it.
if platform.is_windows and platform.is_frozen:
    import time
    filename_template = os.path.join(get_config_dir(), '%s_virtaal.log')
    sys.stdout = _open_frozen_log(filename_template % ('stdout'))
    sys.stderr = _open_frozen_log(filename_template % ('stderr'))
    _launch_marker = _build_launch_marker(time.strftime('%Y-%m-%d %H:%M:%S'))
    sys.stdout.write(_launch_marker)
    sys.stderr.write(_launch_marker)


# Ok, now we can continue with what we actually wanted to do

import builtins as __builtin__
import configparser as ConfigParser
import gettext
import locale
import shutil

from translate.lang import data
from translate.misc import file_discovery

from virtaal.__version__ import ver
from virtaal.support.libi18n.locale import bind_libintl_posix, fix_libintl, fix_locale

# fix_locale(lang) sets these unconditionally (LANG/LC_ALL too on
# Windows) whenever an explicit language is requested below - captured
# here so _install_system_ui_language() can restore them.
_ORIGINAL_LOCALE_ENV = {name: os.environ.get(name) for name in ('LANGUAGE', 'LANG', 'LC_ALL')}

DEBUG = True # Enable debugging by default, while bin/virtaal still disables it by default.
             # This means that if Virtaal (or parts thereof) is run in some other strange way,
             # debugging is enabled.


x_generator = 'Virtaal ' + ver
default_config_name = "virtaal.ini"


def osx_lang():
    """Do some non-posix things to get the language on OSX."""
    import CoreFoundation
    return CoreFoundation.CFLocaleCopyPreferredLanguages()[0]

def get_locale_lang():
    # guess default target lang based on locale, simplify to commonly used form
    try:
        lang = locale.getdefaultlocale(('LANGUAGE', 'LC_ALL', 'LANG'))[0]
        if not lang and platform.is_mac:
           lang = osx_lang()
        if lang:
            return data.simplify_to_common(lang)
    except Exception as e:
        import logging
        logging.warning("%s", e)
    return 'en'

def name():
    import getpass
    name = getpass.getuser()  # username only
    # pwd is only available on UNIX
    try:
        import pwd
        name = pwd.getpwnam(name)[4].split(",")[0]
    except ImportError as _e:
        pass
    return name or ""

def get_default_font():
    default_font = 'monospace'
    font_size = ''

    # First try and get the default font size from GConf
    try:
        import gi
        gi.require_version('GConf', '2.0')
        from gi.repository import GConf
        client = GConf.Client.get_default()
        client.add_dir('/desktop/gnome/interface', GConf.ClientPreloadType.PRELOAD_NONE)
        font_name = client.get_string('/desktop/gnome/interface/monospace_font_name')
        font_size = font_name.split(' ')[-1]
    except ImportError as ie:
        try:
            from gi.repository import Gio
            settings = Gio.Settings.new('org.gnome.desktop.interface')
            font_name = settings.get_string('monospace-font-name')
            if font_name:
                return font_name
        except ImportError as ie2:
            import logging
            logging.debug('Unable to import gconf module: %s', ie2)
    except Exception:
        # Ignore any other errors and try the next method
        pass

    # Get the default font size from Gtk
    if not font_size:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        font_name = Gtk.Label().get_pango_context().get_font_description().to_string()
        font_size = font_name.split(' ')[-1]

    if font_size:
        default_font += ' ' + font_size

    return default_font

defaultfont = get_default_font()

def _repo_root():
    """The checkout root two levels above this file - only meaningful
        for a dev checkout, never called when C{platform.is_frozen}."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _ensure_dev_locale_installed(lang, localedir):
    """A C{pip install -e .} dev checkout never actually gets
        setup.py's own compiled C{mo/<lang>/virtaal.mo} copied into
        C{sys.prefix}'s C{share/locale/} - a known setuptools
        limitation with C{data_files} and editable installs. Self-heal
        it here, once: reuse the repo's own compiled C{mo/} tree if
        C{setup.py} already built one, otherwise compile C{po/<lang>.po}
        directly - translate-toolkit (a hard dependency already) ships
        the exact compiler C{setup.py} itself uses, so this needs
        nothing beyond what's already installed, in a checkout that's
        never run C{pip install -e .} at all."""
    if platform.is_frozen:
        return
    target = os.path.join(localedir, lang, 'LC_MESSAGES', 'virtaal.mo')
    if os.path.isfile(target):
        return

    repo_root = _repo_root()
    source = os.path.join(repo_root, 'mo', lang, 'virtaal.mo')
    if os.path.isfile(source):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(source, target)
        return

    po_file = os.path.join(repo_root, 'po', lang + '.po')
    if not os.path.isfile(po_file):
        return
    from translate.tools.pocompile import convertmo
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(po_file, 'rb') as infile, open(target, 'w') as outfile:
        convertmo(infile, outfile, None)


class Settings:
    """Handles loading/saving settings from/to a configuration file."""

    sections = ["translator", "general", "language", "placeable_state", "plugin_state", "undo"]

    translator =    {
        "name": name(),
        "email": "",
        "team": "",
    }
    general =       {
        "lastdir": "",
        "maximized": '',
        "windowwidth": 796,
        "windowheight": 544,
        "windowx": '',
        "windowy": '',
    }
    language =      {
        "nplurals": 0,
        "plural": None,
        "recentlangs": "",
        "sourcefont": defaultfont,
        "sourcelang": "en",
        "targetfont": defaultfont,
        "targetlang": None,
        "uilang": "",
    }
    placeable_state = {
        "altattrplaceable": "disabled",
        "fileplaceable": "disabled",
    }
    plugin_state =  {
        "_helloworld": "disabled",
    }
    undo = {
        "depth": 10000,
    }

    def __init__(self, filename = None):
        """Load settings, using the given or default filename"""
        if not filename:
            self.filename = os.path.join(get_config_dir(), default_config_name)
        else:
            self.filename = filename
            if not os.path.isfile(self.filename):
                raise Exception

        self.language["targetlang"] = data.simplify_to_common(get_locale_lang())
        self.config = ConfigParser.RawConfigParser()
        self.config_recovery_backup = None
        self.read()

    def read(self):
        """Read the configuration file and set the dictionaries up."""
        self.config_recovery_backup = _read_ini_recovering(self.config, self.filename)
        for section in self.sections:
            if not self.config.has_section(section):
                self.config.add_section(section)

        for key, value in self.config.items("translator"):
            self.translator[key] = value
        for key, value in self.config.items("general"):
            self.general[key] = value
        for key, value in self.config.items("language"):
            self.language[key] = value
        for key, value in self.config.items("placeable_state"):
            self.placeable_state[key] = value
        for key, value in self.config.items("plugin_state"):
            self.plugin_state[key] = value
        for key, value in self.config.items("undo"):
            self.undo[key] = value

        # Make sure we have some kind of font names to work with
        for font in ('sourcefont', 'targetfont'):
            if not self.language[font]:
                self.language[font] = defaultfont

    def write(self):
        """Write the configuration file."""

        # Don't save the default font to file
        fonts = (self.language['sourcefont'], self.language['targetfont'])
        for font in ('sourcefont', 'targetfont'):
            if self.language[font] == defaultfont:
                self.language[font] = ''

        for key in self.translator:
            self.config.set("translator", key, self.translator[key])
        for key in self.general:
            self.config.set("general", key, self.general[key])
        for key in self.language:
            self.config.set("language", key, self.language[key])
        for key in self.placeable_state:
            self.config.set("placeable_state", key, self.placeable_state[key])
        for key in self.plugin_state:
            self.config.set("plugin_state", key, self.plugin_state[key])
        for key in self.undo:
            self.config.set("undo", key, self.undo[key])

        # make sure that the configuration directory exists
        project_dir = os.path.split(self.filename)[0]
        if not os.path.isdir(project_dir):
            os.makedirs(project_dir)
        file = open(self.filename, 'w', encoding='utf-8')
        self.config.write(file)
        file.close()

        self.language['sourcefont'] = fonts[0]
        self.language['targetfont'] = fonts[1]

def _install_explicit_ui_language(lang, languages, fallback):
    """Shared plumbing for installing one specific language's gettext
    catalog: set the process locale, self-heal a dev checkout's
    catalog (see _ensure_dev_locale_installed), install it, and bind
    libintl for Gtk.Builder's C-level gettext calls. `lang` is the
    process locale to request; `languages` is gettext's own lookup
    order, which can fall further back than `lang` alone (e.g. to the
    OS locale, for a saved uilang preference). Used by both startup's
    "uilang saved" branch and set_ui_language()'s explicit-language
    case.

    localedir is passed explicitly - gettext's default search path is
    keyed off sys.base_prefix rather than sys.prefix, so it misses
    translations installed into a venv (which is where
    devsupport/pseudo-translation's own generated locales land) -
    platform.locale_dir additionally corrects for sys.prefix being
    wrong in a frozen build."""
    fix_locale(lang)
    try:
        locale.setlocale(locale.LC_ALL, lang)
    except locale.Error:
        pass
    localedir = platform.locale_dir
    _ensure_dev_locale_installed(lang, localedir)
    gettext.translation('virtaal', localedir=localedir, languages=languages, fallback=fallback).install()
    if not platform.is_windows:
        # Gtk.Builder's own translatable strings go through C-level
        # gettext, not Python's - see bind_libintl_posix's docstring.
        bind_libintl_posix(localedir)


def _install_system_ui_language():
    """Install whatever gettext resolves from the OS's own locale
    environment (LANGUAGE/LC_ALL/LC_MESSAGES/LANG), ignoring any saved
    uilang preference. Shared between startup's "no uilang saved"
    branch and bin/virtaal's --lang=system override."""
    for name, value in _ORIGINAL_LOCALE_ENV.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    fix_locale()
    # Same localedir reason as _install_explicit_ui_language's own
    # docstring. bind_libintl_posix re-points libintl's C-level
    # textdomain too, in case a language was already bound (e.g. a
    # saved uilang preference) - otherwise Gtk.Builder strings stay in
    # that old language while Python-level strings switch.
    localedir = platform.locale_dir
    # Best-guess at what gettext is about to resolve, so a dev checkout
    # self-heals here too (see _ensure_dev_locale_installed) - otherwise
    # this stays untranslated for a language --lang=<code> would find.
    _ensure_dev_locale_installed(get_locale_lang(), localedir)
    try:
        #if the locale is not installed it can cause a traceback
        locale.setlocale(locale.LC_ALL, '')
        gettext.install('virtaal', localedir=localedir)
    except locale.Error as e:
        import logging
        logging.warning("Couldn't set the locale: %s", e)
        # See bug 3109
        __builtin__.__dict__['_'] = lambda s: s
    if not platform.is_windows:
        bind_libintl_posix(localedir)


settings = Settings()

ui_language = settings.language["uilang"]
if ui_language:
    locale_lang = get_locale_lang()
    _install_explicit_ui_language(ui_language, [ui_language, locale_lang], fallback=True)
else:
    _install_system_ui_language()


def get_available_ui_languages():
    """Language codes Virtaal has a real, loadable translation for,
        mapped to display names, sorted by name. Looks both at
        C{platform.locale_dir} (a packaged install) and the repo's own
        C{mo/} tree (a dev checkout - see
        C{_ensure_dev_locale_installed}'s docstring), since either one
        alone can be empty depending on how Virtaal is currently run.

        Doesn't include a "system default" placeholder itself - this
        module is in po/POTFILES.skip (its own _('') probe below would
        otherwise mean gettext isn't set up yet when it runs), so a
        user-facing label belongs in the caller instead."""
    from translate.lang.data import _fixed_names
    from translate.lang.data import languages as toolkit_langs

    codes = set()
    for localedir in (platform.locale_dir, os.path.join(_repo_root(), 'mo')):
        try:
            entries = os.listdir(localedir)
        except OSError:
            continue
        for code in entries:
            if code in ('pseudo', 'pseudo-bidi'):
                continue
            mo_names = ('virtaal.mo', os.path.join('LC_MESSAGES', 'virtaal.mo'))
            if any(os.path.isfile(os.path.join(localedir, code, mo_name)) for mo_name in mo_names):
                codes.add(code)

    def display_name(code):
        name = toolkit_langs[code][0] if code in toolkit_langs else code
        # toolkit's own raw names are the semicolon-joined MARC/ISO 639-2
        # entry ("Catalan; Valencian") - _fixed_names is its own cleanup
        # table for these, defined but never applied by toolkit itself.
        return _fixed_names.get(name, name)

    result = [(code, display_name(code)) for code in codes]
    result.sort(key=lambda pair: pair[1])
    return result

def set_ui_language(lang):
    """Override the UI language after startup - used by bin/virtaal's
    --lang/--pseudo-translation/--pseudo-translation-bidi.

    lang='system' re-resolves the OS's own locale via
    _install_system_ui_language, ignoring any saved uilang preference.
    'en' aliases to 'en_US', and neither raises for a missing catalog -
    English is Virtaal's own source language and ships no catalog of
    its own; any other requested language still raises (fallback=False)
    as a likely typo. The explicit-language case shares
    _install_explicit_ui_language with startup's own "uilang saved"
    branch.
    """
    global ui_language
    if lang == 'system':
        _install_system_ui_language()
        # Matches startup's own `if _(''): ... else: 'en'` guard below -
        # a resolved system locale with no real catalog must report
        # 'en', not the untranslated locale code (aboutdialog.py keys
        # RTL layout off ui_language).
        ui_language = get_locale_lang() if _('') else 'en'
        return

    if lang == 'en':
        lang = 'en_US'
    _install_explicit_ui_language(lang, [lang], fallback=lang == 'en_US')
    # 'en' is this module's canonical "untranslated UI" value elsewhere
    # (the 'system' branch above, the module-level fallback below) -
    # collapse en_US back to it too, so a future `== 'en'` check (like
    # aboutdialog.py's `== 'ar'`) doesn't miss this case.
    ui_language = 'en' if lang == 'en_US' else lang


# Determine the directory the main executable is running from
main_dir = platform.bundle_dir or os.path.dirname(sys.argv[0])


if platform.is_windows and platform.is_frozen:
    fix_libintl(main_dir)

if _(''):
    # If this is true, we have a translated interface
    ui_language = ui_language or get_locale_lang()
else:
    ui_language = 'en'


def get_abs_data_filename(path_parts, basedirs=None):
    """Get the absolute path to the given file- or directory name in Virtaal's
        data directory.

        @type  path_parts: list
        @param path_parts: The path parts that can be joined by os.path.join().
        """
    if basedirs is None:
        basedirs = []
    basedirs += [
        os.path.join(os.path.dirname(__file__), os.path.pardir),
    ]
    return file_discovery.get_abs_data_filename(path_parts, basedirs=basedirs)

def _set_enchant_env_vars(enchant_dir):
    """Point pyenchant at the self-contained dylib bundled at
    enchant_dir (virtaal.spec's own layout: lib/, lib/enchant/,
    share/enchant/) instead of letting it fall through to Homebrew's
    own copy - a second glib/gobject stack in the same process crashes
    cairo/the ObjC runtime, see that spec's own comment."""
    os.environ.setdefault('PYENCHANT_LIBRARY_PATH', os.path.join(enchant_dir, 'lib', 'libenchant.1.dylib'))
    os.environ.setdefault('ENCHANT_MODULE_DIR', os.path.join(enchant_dir, 'lib', 'enchant'))
    os.environ.setdefault('ENCHANT_DATA_DIR', os.path.join(enchant_dir, 'share', 'enchant'))

# Frozen Intel-only - no arm64 build of the bundled dylib exists yet.
if platform.is_mac and platform.is_frozen and platform.is_intel:
    try:
        _set_enchant_env_vars(get_abs_data_filename(["enchant_intel"]))
    except ValueError:
        pass

def load_config(filename, section=None):
    """Load the configuration from the given filename (and optional section
        into a dictionary structure.

        @returns: A 2D-dictionary representing the configuration file if no
            section was specified. Otherwise a simple dictionary representing
            the given configuration section."""
    parser = ConfigParser.RawConfigParser()
    _read_ini_recovering(parser, filename)

    if section:
        if section not in parser.sections():
            return {}
        return dict(parser.items(section))

    conf = {}
    for section in parser.sections():
        conf[section] = dict(parser.items(section))
    return conf

def save_config(filename, config, section=None):
    """Save the given configuration data to the given filename and under the
        given section (if specified).

        @param config: A dictionary containing the configuration section data
            if C{section} was specified. Otherwise, if C{section} is not
            specified, it should be a 2D-dictionary representing the entire
            configuration file."""
    parser = ConfigParser.ConfigParser()
    _read_ini_recovering(parser, filename)

    if section:
        config = {section: config}
        for sect in config.keys():
            parser.remove_section(sect)
    else:
        # config is the entire file's content per this function's own
        # contract above - a section missing from it (e.g. an item the
        # caller deleted since the last save) must not survive from
        # what's already on disk.
        for sect in parser.sections():
            parser.remove_section(sect)

    for section, section_conf in config.items():
        if section not in parser.sections():
            parser.add_section(section)
        for key, value in section_conf.items():
            if isinstance(value, list):
                value = ','.join(value)
            parser.set(section, key, str(value))

    conffile = open(filename, 'w', encoding='utf-8')
    parser.write(conffile)
    conffile.close()
