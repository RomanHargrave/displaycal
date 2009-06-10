#!/bin/sh

dist=debian5

dpkg_host_arch=`perl -e "use Dpkg::Arch qw(get_host_arch);print get_host_arch();"`
platform=`uname -m`
version=`python -c "from dispcalGUI import meta;print meta.version"`

# Python 2.5 DEB
log=dispcalGUI_$version-py2.5-$dist.$platform.bdist_deb.log
/usr/bin/python2.5 setup.py bdist_deb --cfg=$dist --force-arch=$platform --use-distutils 2>&1 | tee $log
mv -f dist/dispcalgui_$version-1_$dpkg_host_arch.deb dist/dispcalgui_$version-py2.5-$dist-1_$platform.deb 2>&1 | tee -a $log
mv -f dist/dispcalGUI-$version-1.$platform.rpm dist/dispcalGUI-$version-py2.5-$dist-1.$platform.rpm 2>&1 | tee -a $log
mv -f dist/dispcalGUI-$version-1.src.rpm dist/dispcalGUI-$version-py2.5-$dist-1.src.rpm 2>&1 | tee -a $log
