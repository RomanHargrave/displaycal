#!/bin/sh

# Make sure __version__.py is current
./setup.py

version=`python -c "from dispcalGUI import meta;print meta.version"`

# Source tarball
./setup.py sdist --use-distutils 2>&1 | tee dispcalGUI-$version.sdist.log

# 0install
util/dist_0install.sh

# App bundle & dmg
./setup.py bdist_standalone 2>&1 | tee dispcalGUI-$version.bdist_standalone_osx.log
./setup.py bdist_appdmg 2>&1 | tee -a dispcalGUI-$version.bdist_standalone_osx.log

# Cleanup
util/tidy_dist.py
