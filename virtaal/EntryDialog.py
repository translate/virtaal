import gtk

def EntryDialog(title):
    dlg = gtk.Dialog(title)
    dlg.set_size_request(450, 100)
    dlg.show()

    entry = gtk.Entry()
    entry.show()
    entry.grab_focus()
    entry.set_activates_default(True)
    dlg.vbox.pack_start(entry)

    dlg.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    dlg.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
    dlg.set_default_response(gtk.RESPONSE_OK)
    response = dlg.run()

    text = None
    if response == gtk.RESPONSE_OK:
        text = entry.get_text().decode('utf-8')
    dlg.destroy()
    return text
