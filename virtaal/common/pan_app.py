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
from .utils import get_unicode


def _read_ini_recovering(parser, filename):
    """Read filename into parser, recovering from a corrupt/unreadable
    file instead of crashing - it may be a user's own hand-edited file
    they'd want back, so back it up rather than overwriting or
    discarding it silently, and leave parser empty so the caller falls
    back to its own defaults.

    Returns the backup path, or None if the file was fine (or absent)."""
    try:
        parser.read(filename)
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

    confdir = get_unicode(confdir)
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

from translate.lang import data
from translate.misc import file_discovery

from virtaal.__version__ import ver
from virtaal.support.libi18n.locale import bind_libintl_posix, fix_libintl, fix_locale

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
    name = get_unicode(getpass.getuser())  # username only
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
        from gi.repository import Gio
        settings = Gio.Settings.new('org.gnome.desktop.interface')
        font_name = settings.get_string('monospace-font-name')
        if font_name:
            return font_name
    except ImportError as ie:
        import logging
        logging.debug('Unable to import gconf module: %s', ie)
    except Exception:
        # Ignore any other errors and try the next method
        pass

    # Get the default font size from Gtk
    if not font_size:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        style_context = Gtk.Label().get_style_context()
        font_name = style_context.get_font(style_context.get_state()).to_string()
        font_size = font_name.split(' ')[-1]

    if font_size:
        default_font += ' ' + font_size

    return default_font

defaultfont = get_default_font()


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
        file = open(self.filename, 'w')
        self.config.write(file)
        file.close()

        self.language['sourcefont'] = fonts[0]
        self.language['targetfont'] = fonts[1]

settings = Settings()

ui_language = settings.language["uilang"]
if ui_language:
    locale_lang = get_locale_lang()
    fix_locale(ui_language)
    try:
        locale.setlocale(locale.LC_ALL, ui_language)
    except locale.Error:
        pass
    languages = [ui_language, locale_lang]
    gettext.translation('virtaal', languages=languages, fallback=True).install()
else:
    fix_locale()
    try:
        #if the locale is not installed it can cause a traceback
        locale.setlocale(locale.LC_ALL, '')
        gettext.install('virtaal')
    except locale.Error as e:
        import logging
        logging.warning("Couldn't set the locale: %s", e)
        # See bug 3109
        __builtin__.__dict__['_'] = lambda s: s


def set_ui_language(lang):
    """Override the UI language after startup - used by bin/virtaal's
    --pseudo-translation/--pseudo-translation-bidi. fallback=False: a
    missing catalog should raise, not silently fall back to English.

    localedir is passed explicitly - gettext's default search path is
    keyed off sys.base_prefix rather than sys.prefix, so it misses
    translations installed into a venv (which is where
    devsupport/pseudo-translation's own generated locales land).
    """
    global ui_language
    fix_locale(lang)
    try:
        locale.setlocale(locale.LC_ALL, lang)
    except locale.Error:
        pass
    localedir = os.path.join(sys.prefix, 'share', 'locale')
    gettext.translation('virtaal', localedir=localedir, languages=[lang], fallback=False).install()
    if not platform.is_windows:
        # Gtk.Builder's own translatable strings go through C-level
        # gettext, not Python's - see bind_libintl_posix's docstring.
        bind_libintl_posix(localedir)
    ui_language = lang


# Determine the directory the main executable is running from
main_dir = ''
if platform.is_frozen:
    main_dir = os.path.dirname(get_unicode(sys.executable))
else:
    main_dir = os.path.dirname(get_unicode(sys.argv[0]))


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
        os.path.join(os.path.dirname(get_unicode(__file__)), os.path.pardir),
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

    conffile = open(filename, 'w')
    parser.write(conffile)
    conffile.close()
