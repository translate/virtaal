import gettext
import gtk.glade
import location

APP = 'virtaal'
DIR = location.i18n_dir
 
gettext.bindtextdomain(APP, DIR)
gettext.textdomain(APP)
gtk.glade.bindtextdomain(APP, DIR)
gtk.glade.textdomain(APP)

_ = gettext.gettext # the i18n function :)
