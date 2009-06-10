#!/bin/sh

dist=mandriva2009.1

platform=`uname -m`
version=`python -c "from dispcalGUI import meta;print meta.version"`

# Python 2.6 RPM
log=dispcalGUI-$version-py2.6-$dist.$platform.bdist_rpm.log
/usr/bin/python2.6 setup.py bdist_rpm --cfg=$dist-argyll --force-arch=$platform --skip-instrument-configuration-files --use-distutils 2>&1 | tee $log
mv -f dist/dispcalGUI-$version-1.$platform.rpm dist/dispcalGUI-$version-py2.6-$dist-argyll-1.$platform.rpm 2>&1 | tee -a $log
mv -f dist/dispcalGUI-$version-1.src.rpm dist/dispcalGUI-$version-py2.6-$dist-argyll-1.src.rpm 2>&1 | tee -a $log
