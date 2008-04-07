import StringIO
import gtk.glade
from ConfigParser import DuplicateSectionError, NoSectionError
#from widget_state import dump_state, load_state

default_config = '''
'''

def get_widgets(self):
    """Return an iterator which produces (widget_name, widget) pairs.

    glade.XML.get_widget_prefix returns all widgets with names starting with the
    supplied string; so if we call get_widget_prefix(''), we get all the widgets
    in the loaded glade file!
    """
    return ((gtk.glade.get_widget_name(w), w) for w in  self.get_widget_prefix(''))


def dump_gtk_state(self, cfg):
    """Enumerate the widgets in the loaded glade file.

    For each widget, create a section in the configuration file represented by 'cfg'.
    Then, write the widget state using the dictionary produced by dump_state to the
    widget's section in the 'cfg' file.
    """
    for widget_name, widget in self.get_widgets():
        try:
            cfg.add_section(widget_name)
        except DuplicateSectionError, e:
            pass

        for key, val in dump_state(widget).iteritems():
            cfg.set(widget_name, key, str(val))


def load_gtk_state(self, cfg):
    for widget_name, widget in self.get_widgets():
        try:
            load_state(widget, dict(cfg.items(widget_name)))
        except KeyError, e:
            pass
        except NoSectionError, e:
            pass


def connect(self, context):
    """Enumerate the methods in the object 'context''s class. For each method, create a
    (name, function) pair, with the function name and a bound method (binding is done to
    the object 'context' via getattr(context, name)).

    Now, create a dictionary out of these pairs. Fincally pass the dictionary to
    signal_autoconnect, which will bind the signals defined in the glade file to our
    methods."""
    handlers = dict((name, getattr(context, name)) for name in context.__class__.__dict__)
    self.signal_autoconnect(handlers)
