
try:
    #from iniparse import ConfigParser
    import iniparse as ConfigParser
except ImportError, e:
    import ConfigParser
import os
import locale, gettext
import pygtk
pygtk.require("2.0")
import gobject, gtk
import gettext
_ = gettext.gettext

from __version__ import ver

x_generator = 'VirTaal ' + ver
default_config = "~/.locamotion/virtaal.ini"

def name():
    # pwd is only available on UNIX
    try:
        import pwd
        import getpass
    except ImportError, e:
        return u""
    return pwd.getpwnam(getpass.getuser())[4]

class Settings:
    """Handles loading/saving settings from/to a configuration file."""

    sections = ["translator", "general", "language"]

    translator =    {
            "name": name(),
            "email": "",
            "team": "",
    }
    general =       {
            "lastdir": "",
            "windowheight": 620,
            "windowwidth": 400,
    }
    language =      {
            "uilang": None,
            "contentlang": None,
    }

    def __init__(self, filename = None):
        """Load settings, using the given or default filename"""
        if not filename:
            self.filename = os.path.expanduser(default_config)
        else:
            self.filename = filename

        try:
            lang = locale.getlocale()[0]
            self.language["uilang"] = lang
            self.language["contentlang"] = lang
        except:
            pass
        self.config = ConfigParser.ConfigParser()
        self.read()

    def read(self):
        """Read the configuration file and set the dictionaries up."""
        self.config.read(self.filename)
    
        for section in self.sections:
            if not self.config.has_section(section):
                self.config.add_section(section)
    
        for key, value in self.config.items("translator"):
            self.translator[key] = value
        for key, value in self.config.items("general"):
            self.general[key] = value
        for key, value in self.config.items("language"):
            self.language[key] = value
        
    def write(self):
        """Write the configuration file."""        
        for key in self.translator:
            self.config.set("translator", key, self.translator[key])
        for key in self.general:
            self.config.set("general", key, self.general[key])
        for key in self.language:
            self.config.set("language", key, self.language[key])

        # make sure that the configuration directory exists
        project_dir = os.path.split(self.filename)[0]
        if not os.path.isdir(project_dir): 
            os.makedirs(project_dir)
        file = open(self.filename, 'w')
        self.config.write(file)
        file.close()
 

#static list of all the Instrument files (to prevent having to reimport files).
instrumentPropertyList = []
_alreadyCached = False
_cacheGeneratorObject = None

def _cacheInstrumentsGenerator(alreadyLoadedTypes=[]):
    """
    Yields a loaded Instrument everytime this method is called,
    so that the gui isn't blocked while loading many Instruments.
    If an Instrument's type is already in alreadyLoadedTypes,
    it is considered a duplicate and it's not loaded.
    
    Parameters:
        alreadyLoadedTypes -- array containing the already loaded Instrument types.
        
    Returns:
        the loaded Instrument. *CHECK*
    """    
    try:
        #getlocale() will usually return  a tuple like: ('en_GB', 'UTF-8')
        lang = locale.getlocale()[0]
    except:
        lang = None
    for instr_path in INSTR_PATHS:
        if not os.path.exists(instr_path):
            continue
        instrFiles = [x for x in os.listdir(instr_path) if x.endswith(".instr")]
        for f in instrFiles:
            config = ConfigParser.SafeConfigParser()
            try:
                config.read(os.path.join(instr_path, f))
            except ConfigParser.MissingSectionHeaderError,e:
                debug("Instrument file %s in %s is corrupt or invalid, not loading"%(f,instr_path))
                continue    

            if config.has_option('core', 'type') and config.has_option('core', 'icon'):
                icon = config.get('core', 'icon')
                type = config.get('core', 'type')
            else:
                continue
            #don't load duplicate instruments
            if type in alreadyLoadedTypes:
                continue
        
            if lang and config.has_option('i18n', lang):
                name = config.get('i18n', lang)
            elif lang and config.has_option('i18n', lang.split("_")[0]):
                #in case lang was 'de_DE', use only 'de'
                name = config.get('i18n', lang.split("_")[0])
            elif config.has_option('i18n', 'en'):
                #fall back on english (or a PO translation, if there is any)
                name = _(config.get( 'i18n', 'en'))
            else:
                continue
            name = unicode(name, "UTF-8")
            pixbufPath = os.path.join(instr_path, "images", icon)
            pixbuf = gtk.gdk.pixbuf_new_from_file(pixbufPath)
            
            # add instrument to defaults list if it's a defaults
            if instr_path == INSTR_PATHS[0]:
                DEFAULT_INSTRUMENTS.append(type)
                
            yield (name, type, pixbuf, pixbufPath)


"""
Used for launching the correct help file:
    True -- Jokosher's running locally by the user. Use the help file from
            the help subdirectory.
    False -- Jokosher has been installed system-wide. Use yelp's automatic
            help file selection.
"""
USE_LOCAL_HELP = False

"""
Global paths, so all methods can access them.
If JOKOSHER_DATA_PATH is not set, that is, Jokosher is running locally,
use paths relative to the current running directory instead of /usr ones.
"""
data_path = os.getenv("JOKOSHER_DATA_PATH")
if data_path:
    INSTR_PATHS = (os.path.join(data_path, "Instruments"), os.path.expanduser("~/.jokosher/instruments"))
    GLADE_PATH = os.path.join(data_path, "Jokosher.glade")
else:
    data_path = os.path.dirname(os.path.abspath(__file__))
    INSTR_PATHS = (os.path.join(data_path, "..", "Instruments"), os.path.expanduser("~/.jokosher/instruments"))
    GLADE_PATH = os.path.join(data_path, "Jokosher.glade")
    LOCALE_PATH = os.path.join(data_path, "..", "locale")

#delete the 0.1 jokosher config file
if os.path.isfile(os.path.expanduser("~/.jokosher")):
    try:
        os.remove(os.path.expanduser("~/.jokosher"))
    except:
        raise "Failed to delete old user config file %s" % new_dir
# create a couple dirs to avoid having problems creating a non-existing
# directory inside another non-existing directory
for directory in ['extensions', 'instruments', 'instruments/images', 
        'presets', 'presets/effects', 'presets/mixdown', 'mixdownprofiles']:
    new_dir = os.path.join(os.path.expanduser("~/.jokosher/"), directory)
    if not os.path.isdir(new_dir):
        try:
            os.makedirs(new_dir)
        except:
            raise "Failed to create user config directory %s" % new_dir

#TODO: make this a list with the system path and home directory path
EFFECT_PRESETS_PATH = os.path.expanduser("~/.jokosher/presets/effects")

IMAGE_PATH = os.getenv("JOKOSHER_IMAGE_PATH")
if not IMAGE_PATH:
    IMAGE_PATH = os.path.join(data_path, "..", "images")

LOCALE_PATH = os.getenv("JOKOSHER_LOCALE_PATH")
if not LOCALE_PATH:
    LOCALE_PATH = os.path.join(data_path, "..", "locale")

HELP_PATH = os.getenv("JOKOSHER_HELP_PATH")
if not HELP_PATH:
    USE_LOCAL_HELP = True
    
    # change the local help file to match the current locale
    current_locale = "C"
    if locale.getlocale()[0] and not locale.getlocale()[0].startswith("en", 0, 2):
        current_locale = locale.getlocale()[0][:2]
        
    HELP_PATH = os.path.join(data_path, "..", "help/jokosher",
                             current_locale, "jokosher.xml")
    
    # use C (en) as the default help fallback
    if not os.path.exists(HELP_PATH):
        HELP_PATH = os.path.join(data_path, "..", "help/jokosher/C/jokosher.xml")


""" ExtensionManager data """
AVAILABLE_EXTENSIONS = []
INSTRUMENT_HEADER_WIDTH = 0

""" Locale constant """
LOCALE_APP = "jokosher"

""" Default Instruments """
DEFAULT_INSTRUMENTS = []

settings = Settings()
