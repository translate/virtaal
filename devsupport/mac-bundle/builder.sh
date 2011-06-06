#!/bin/bash

## Setup jhbuild your .jhbuild-custom should contain the following
#setup_sdk(target="10.5", sdk_version="10.5", architectures=["i386"])
#build_policy = "updated-deps"
#moduleset="http://github.com/jralls/gtk-osx-build/raw/master/modulesets-stable/gtk-osx.modules"
#_gtk_osx_use_jhbuild_python = True # Needed because we're going to bundle Virtaal

jhbuild=~/.local/bin/jhbuild
# For interactive builds set this to empty
jhbuild_options="--no-interact"
src_dir=/Users/dev/gtk/source/virtaal-trunk/
bundle_dir=/Users/dev/gtk/source/virtaal-trunk/devsupport/mac-bundle/
virtaal_modules=${bundle_dir}/virtaal.modules
app_name=Virtaal
app_version=0.7.0

# Actual build
$jhbuild $jhbuild_options bootstrap --ignore-system &&
$jhbuild $jhbuild_options --moduleset=$virtaal_modules build berkeleydb &&
$jhbuild $jhbuild_options --moduleset=bootstrap.modules buildone --force python && # This rebuilds python - oh well
$jhbuild $jhbuild_options build intltool meta-gtk-osx-bootstrap meta-gtk-osx-core meta-gtk-osx-python &&
$jhbuild $jhbuild_options --moduleset=$virtaal_modules build virtaal

# Test the build
#jhbuild shell
#virtaal


## Bundle the build
# TODO build and get ige-mac-bundler
ige_mac_bundler=~/.local/bin/ige-mac-bundler
$jhbuild run $SHELL -c 'chmod -w $PREFIX/lib/libpython2.7.dylib'
$jhbuild run $SHELL -c "$ige_mac_bundler $bundle_dir/virtaal.bundle"


## Make a .dmg file
# Mostly taken from http://endrift.com/blog/2010/06/14/dmg-files-volume-icons-cli/
volume_name="$app_name"
dmg_file=~/Desktop/$app_name-$app_version-mac-beta-1.dmg
raw_dmg_file=~/Desktop/raw-$app_name-$app_version-mac-beta-1.dmg
tmp=~/Desktop/tmp-$app_name

# Stage files
rm -rf $tmp
mkdir -p $tmp
mv ~/Desktop/Virtaal.app $tmp
cp -p $src_dir/README $tmp/ReadMe.txt
cp -p $src_dir/LICENSE $tmp/License.txt
(cd $tmp; ln -s /Applications)

# Set background
mkdir -p $tmp/.background
cp -p $bundle_dir/virtaal_DMG_background.png $tmp/.background

# Set Volume Icon
cp $bundle_dir/icons/VolumeIcon_virtaal.icns $tmp/.VolumeIcon.icns
SetFile -c icnC $tmp/.VolumeIcon.icns

# Lets do some internal layout
read -p "Pause to allow you to setup the folder" pause

# Make an image
hdiutil create -srcfolder $tmp -volname $volume_name -format UDRW -ov $raw_dmg_file

# Sort out the Volume Icon
rm -rf $tmp
mkdir -p $tmp
hdiutil attach $raw_dmg_file -mountpoint $tmp
SetFile -a C $tmp
hdiutil detach $tmp

# Make final DMG
rm -rf $tmp
rm -f $dmg_file
hdiutil convert $raw_dmg_file -format UDZO -imagekey zlib-level=9 -o $dmg_file 
rm -f $raw_dmg_file
