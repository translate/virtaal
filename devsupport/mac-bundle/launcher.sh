#!/bin/sh

name="`basename $0`"
bundle=`dirname "$0"`/../..
bundle_contents="$bundle"/Contents
bundle_res="$bundle_contents"/Resources

# Set $PYTHON to point inside the bundle
export PYTHON="$bundle_contents/MacOS/python"
# Python 2.7 seems to need this
export PYTHONHOME="$bundle_res"
# Set PATH so that Virtaal can launch tmserver
export PATH=$PATH:"$bundle_contents"/MacOS

# Note that we're calling $PYTHON here to override the version in
# the shebang.
$EXEC $PYTHON "$bundle_contents/MacOS/runvirtaal.py"
