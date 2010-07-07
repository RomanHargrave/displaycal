#!/bin/sh

dist=debian5

dpkg_host_arch=`perl -e "use Dpkg::Arch qw(get_host_arch);print get_host_arch();"`
platform=`uname -m`
version=`python -c "from dispcalGUI import meta;print meta.version"`

# Python 2.5 DEB
log=dispcalGUI_$version-$dist.$platform.bdist_deb.log
/usr/bin/python2.5 setup.py bdist_deb --cfg=$dist --force-arch=$platform --use-distutils 2>&1 | tee $log
