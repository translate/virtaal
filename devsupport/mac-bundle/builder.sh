#!/bin/bash

## Setup jhbuild your .jhbuild-custom should contain the following
#setup_sdk(target="10.5", sdk_version="10.5", architectures=["i386"])
#build_policy = "updated-deps"
#moduleset="http://github.com/jralls/gtk-osx-build/raw/master/modulesets-stable/gtk-osx.modules"
#_gtk_osx_use_jhbuild_python = True # Needed because we're going to bundle Virtaal

jhbuild=~/.local/bin/jhbuild
# For interactive builds set this to empty
jhbuild_options="--no-interact"
virtaal_mac=/Users/dev/gtk/source/virtaal-trunk/devsupport/mac-bundle/
virtaal_modules=${virtaal_mac}/virtaal.modules

# Actual build
$jhbuild $jhbuild_options bootstrap --ignore-system &&
$jhbuild $jhbuild_options --moduleset=$virtaal_modules build berkeleydb &&
$jhbuild $jhbuild_options --moduleset=bootstrap.modules buildone --force python && # This rebuilds python - oh well
$jhbuild $jhbuild_options build intltool meta-gtk-osx-bootstrap meta-gtk-osx-core meta-gtk-osx-python &&
$jhbuild $jhbuild_options --moduleset=$virtaal_modules build virtaal

# Test the build
#jhbuild shell
#virtaal

# Buncle the build
# TODO build and get ige-mac-bundler
ige_mac_bundler=~/.local/bin/ige-mac-bundler
$jhbuild run $SHELL -c 'chmod -w $PREFIX/lib/libpython2.7.dylib'
$jhbuild run $SHELL -c '$ige_mac_bundler $virtaal_mac/virtaal.bundle'

# Make a .dmg file
echo "Make dmg based on gramps guidelines"


