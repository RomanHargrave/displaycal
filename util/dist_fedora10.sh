#!/bin/sh

dist=fedora10

version=`python -c "from dispcalGUI import meta;print meta.version"`

# Python 2.5 RPM for Fedora Argyll 1.0.3 package
/usr/bin/python2.5 setup.py bdist_rpm --cfg=$dist-argyll --skip-instrument-configuration-files --use-distutils 2>&1 | tee dispcalGUI-$version-py2.5-$dist-argyll.bdist_rpm.log
mv -f dist/dispcalGUI-$version-1.*.rpm dist/dispcalGUI-$version-py2.5-$dist-argyll-1.*.rpm
mv -f dist/dispcalGUI-$version-1.src.rpm dist/dispcalGUI-$version-py2.5-$dist-argyll-1.src.rpm

# Python 2.5 RPM for standalone Argyll executables
/usr/bin/python2.5 setup.py bdist_rpm --cfg=$dist --use-distutils 2>&1 | tee dispcalGUI-$version-py2.5-$dist.bdist_rpm.log
mv -f dist/dispcalGUI-$version-1.*.rpm dist/dispcalGUI-$version-py2.5-$dist-1.*.rpm
mv -f dist/dispcalGUI-$version-1.src.rpm dist/dispcalGUI-$version-py2.5-$dist-1.src.rpm
