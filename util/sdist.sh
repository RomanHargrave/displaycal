#!/bin/sh

version=`python -c "from dispcalGUI import meta;print meta.version"`

# Source tarball
./setup.py sdist 0install $* --use-distutils 2>&1 | tee dispcalGUI-$version.sdist.log
