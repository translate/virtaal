#!/usr/bin/python
"""
Quick and dirty autocorr file downloader

Downloads all available autocor files from OpenOffice.org Mercurial repository.
Works in the current directory.
"""

import urllib
import re

HG_AUTOCORR_DIR = 'http://hg.services.openoffice.org/DEV300/file/tip/extras/source/autotext/lang'
FILE_PATTERN = re.compile('acor_(.*).dat')
SKIP_LANGS = ("eu",) # garbage == en-US

langs = []

print "Getting language list..."

for line in urllib.urlopen('%s/?style=raw' % HG_AUTOCORR_DIR).readlines():
    if line.startswith("drwx"): # readable, executable directory
        lang = line.split()[1]
        if lang not in SKIP_LANGS:
            langs.append(lang)
        else:
            print "Skipping %s" % lang

print "done"
print "Available languages: %s" % " ".join(langs)

for lang in langs:
    for line in urllib.urlopen('%s/%s/?style=raw' % (HG_AUTOCORR_DIR, lang)).readlines():
        try:
            chmod, size, fname = line.split()
            if FILE_PATTERN.match(fname):
                print "Downloading %s (%s bytes)..." % (fname, size)
                file_contents = urllib.urlopen('%s/%s/%s?style=raw' %
                                               (HG_AUTOCORR_DIR, lang, fname)).read()
                file(fname, "wb").write(file_contents)
                print "done"
        except ValueError:
            # don't process empty lines
            pass
