#!/bin/bash

xgettext --language=Python \
         --msgid-bugs-address=translate-devel@lists.sourceforge.net \
         --copyright-holder="Zuza Software Foundation (Translate.org.za)" \
         --output=po/virtaal.pot \
         $(find virtaal/ -name "*.py")
