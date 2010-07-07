#!/bin/sh

dist=mandriva2009.1

platform=`uname -m`
version=`python -c "from dispcalGUI import meta;print meta.version"`

# Python 2.6 RPM
log=dispcalGUI-$version-$dist.$platform.bdist_rpm.log
/usr/bin/python2.6 setup.py bdist_rpm --cfg=$dist --force-arch=$platform --use-distutils 2>&1 | tee $log
