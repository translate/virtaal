#!/bin/bash

## Setup jhbuild your .jhbuild-custom should contain the following
#setup_sdk(target="10.5", sdk_version="10.5", architectures=["i386"])
#build_policy = "updated-deps"
#moduleset="http://github.com/jralls/gtk-osx-build/raw/master/modulesets-stable/gtk-osx.modules"
#_gtk_osx_use_jhbuild_python = True # Needed because we're going to bundle Virtaal

jhbuild=~/.local/bin/jhbuild
virtaal_mac=/Users/dev/gtk/source/virtaal-trunk/devsupport/mac-bundle/
virtaal_modules=${virtaal_mac}/virtaal.modules

# Actual build
$jhbuild bootstrap --ignore-system &&
$jhbuild --moduleset=$virtaal_modules build berkeleydb &&
$jhbuild --moduleset=bootstrap.modules buildone --force python && # This rebuilds python - oh well
$jhbuild build intltool meta-gtk-osx-bootstrap meta-gtk-osx-core meta-gtk-osx-python &&
$jhbuild --moduleset=$virtaal_modules build virtaal

# Test the build
#jhbuild shell
#virtaal

# Buncle the build
# TODO build and get ige-mac-bundler
$jhbuild shell
chmod +w $PREFIX/lib/libpython2.7.dylib
ige-mac-bundler $virtaal_mac/virtaal.bundle

# Make a .dmg file
echo "Make dmg based on gramps guidelines"


