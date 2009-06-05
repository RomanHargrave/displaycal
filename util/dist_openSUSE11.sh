#!/bin/sh

dist=openSUSE11

version=`python -c "from dispcalGUI import meta;print meta.version"`

# Python 2.5 RPM
/usr/bin/python2.5 setup.py bdist_rpm --cfg=$dist --use-distutils 2>&1 | tee rpm-py2.5-$dist.log
mv -f dist/dispcalGUI-$version-1.i586.rpm dist/dispcalGUI-$version-py2.5-$dist-1.i586.rpm

# Python 2.6 RPM
/usr/bin/python2.6 setup.py bdist_rpm --cfg=$dist --use-distutils 2>&1 | tee rpm-py2.6-$dist.log
mv -f dist/dispcalGUI-$version-1.i586.rpm dist/dispcalGUI-$version-py2.6-$dist-1.i586.rpm
