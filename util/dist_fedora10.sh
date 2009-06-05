#!/bin/sh

dist=fedora10

version=`python -c "from dispcalGUI import meta;print meta.version"`

# Python 2.5 RPM for Fedora Argyll 1.0.3 package
/usr/bin/python2.5 setup.py bdist_rpm --cfg=$dist-argyll --use-distutils 2>&1 | tee rpm-py2.5-$dist-argyll.log
mv -f dist/dispcalGUI-$version-1.i386.rpm dist/dispcalGUI-$version-py2.5-$dist-argyll-1.i386.rpm

# Python 2.5 RPM for standalone Argyll executables
/usr/bin/python2.5 setup.py bdist_rpm --cfg=$dist --skip-instrument-configuration-files --use-distutils 2>&1 | tee rpm-py2.5-$dist.log
mv -f dist/dispcalGUI-$version-1.i386.rpm dist/dispcalGUI-$version-py2.5-$dist-1.i386.rpm
