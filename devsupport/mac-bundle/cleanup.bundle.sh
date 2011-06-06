#!/bin/bash

bundle=~/Desktop/Virtaal.app/Contents/Resources

# Drop anything to do with tests
rm -rf ${bundle}/lib/python2.7/email/test
rm -rf ${bundle}/lib/python2.7/test
rm -rf ${bundle}/lib/python2.7/lib-tk
rm -rf ${bundle}/lib/python2.7/lib2to3/tests
rm -rf ${bundle}/lib/python2.7/site-packages/virtaal/test
rm -rf ${bundle}/lib/python2.7/json/tests
rm -rf ${bundle}/lib/python2.7/sqlite3/test
rm -rf ${bundle}/lib/python2.7/site-packages/distribute-0.6.10-py2.7.egg/setuptools/tests
rm -rf ${bundle}/lib/python2.7/unittest/test
rm -rf ${bundle}/lib/python2.7/distutils/tests
rm -rf ${bundle}/lib/python2.7/bsddb/test
rm -rf ${bundle}/lib/python2.7/ctypes/test

# Old Carbon based tools
rm -rf ${bundle}/lib/python2.7/plat-mac

# Remove toolkit and virtaal tests
rm -rf $(find ${bundle}/lib/python2.7 -name "test_*.py")
