#!/bin/sh

# Make sure __version__.py is current
./setup.py

distname=`python -c "import platform; print '%s %s %s' % getattr(platform, 'linux_distribution', platform.dist)()"`
dist=`python -c "import platform; print ('%s_%s_%s' % getattr(platform, 'linux_distribution', platform.dist)()).lower()"`
dpkg_host_arch=`perl -e "use Dpkg::Arch qw(get_host_arch);print get_host_arch();"`
platform=`uname -m`
python_version=`python -c "import sys;print sys.version[:3]"`
python=`which python$python_version 2>/dev/null || which python`
version=`python -c "from dispcalGUI import meta;print meta.version"`

# DEB
log=dispcalGUI_$version-$dist.$dpkg_host_arch.bdist_deb.log
$python setup.py bdist_deb --cfg=ubuntu --distribution-name="$distname" --force-arch=$platform --python=$python --use-distutils 2>&1 | tee "$log"

# Cleanup
util/tidy_dist.py
