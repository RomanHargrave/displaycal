#!/bin/sh

dist=fedora10

platform=`uname -m`
version=`python -c "from dispcalGUI import meta;print meta.version"`

# Python 2.5 RPM for Fedora Argyll 1.0.3 package
log=dispcalGUI-$version-py2.5-$dist-argyll.$platform.bdist_rpm.log
/usr/bin/python2.5 setup.py bdist_rpm --cfg=$dist-argyll --force-arch=$platform --skip-instrument-configuration-files --use-distutils 2>&1 | tee $log
mv -f dist/dispcalGUI-$version-1.$platform.rpm dist/dispcalGUI-$version-py2.5-$dist-argyll-1.$platform.rpm 2>&1 | tee -a $log
mv -f dist/dispcalGUI-$version-1.src.rpm dist/dispcalGUI-$version-py2.5-$dist-argyll-1.src.rpm 2>&1 | tee -a $log

# Python 2.5 RPM for standalone Argyll executables
log=dispcalGUI-$version-py2.5-$dist.$platform.bdist_rpm.log
/usr/bin/python2.5 setup.py bdist_rpm --cfg=$dist --force-arch=$platform --use-distutils 2>&1 | tee $log
mv -f dist/dispcalGUI-$version-1.$platform.rpm dist/dispcalGUI-$version-py2.5-$dist-1.$platform.rpm 2>&1 | tee -a $log
mv -f dist/dispcalGUI-$version-1.src.rpm dist/dispcalGUI-$version-py2.5-$dist-1.src.rpm 2>&1 | tee -a $log
