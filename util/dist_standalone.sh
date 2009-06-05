#!/bin/sh

platform=`python -c "from distutils.util import get_platform;print get_platform()"`
python_version=`python -c "import sys;print sys.version[:3]"`
version=`python -c "from dispcalGUI import meta;print meta.version"`

# Standalone executable
./setup.py bdist_pyi -F --use-distutils 2>&1 | tee pyi.log

# ZIP
cd dist/pyi.$platform-$python_version-onefile
zip -9 -r dispcalGUI-$version dispcalGUI-$version
