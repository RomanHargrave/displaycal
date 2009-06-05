#!/bin/sh

version=`python -c "from dispcalGUI import meta;print meta.version"`

# Source tarball
./setup.py sdist --use-distutils 2>&1 | tee sdist.log

