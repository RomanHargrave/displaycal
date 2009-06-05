#!/bin/sh

dist=ubuntu9

version=`python -c "from dispcalGUI import meta;print meta.version"`

# Python 2.6 DEB
/usr/bin/python2.6 setup.py bdist_rpm --cfg=$dist --use-distutils 2>&1 | tee deb-py2.6-$dist.log
mv -f dist/dispcalgui_$version-1_i386.deb dist/dispcalgui_$version-py2.6-$dist-1_i386.deb
