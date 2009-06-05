#!/bin/sh

platform=`python -c "from distutils.util import get_platform;print get_platform()"`
python_version=`python -c "import sys;print sys.version[:3]"`
version=`python -c "from dispcalGUI import meta;print meta.version"`

# Standalone executable
log=dispcalGUI-$version.pyi.$platform-py$python_version-onefile.log
python2.6 setup.py bdist_pyi -F --use-distutils 2>&1 | tee $log

# ZIP
cd dist/pyi.$platform-py$python_version-onefile
tar -pczf dispcalGUI-$version-$platform.tar.gz dispcalGUI-$version 2>&1 | tee -a $log
