#!/bin/sh

# Make sure __version__.py is current
./setup.py

distname=`python -c "import platform; print '%s %s %s' % getattr(platform, 'linux_distribution', platform.dist)()"`
dist=`python -c "import platform; print ('%s_%s_%s' % getattr(platform, 'linux_distribution', platform.dist)()).lower()"`
platform=`uname -m`
python_version=`python -c "import sys;print sys.version[:3]"`
python=`which python$python_version 2>/dev/null || which python`
version=`python -c "from DisplayCAL import meta;print meta.version"`

# RPM
log=DisplayCAL-$version-$dist.$platform.bdist_rpm.log
$python setup.py bdist_rpm --cfg=mandriva64 --distribution-name="$distname" --force-arch=$platform --python=$python --use-distutils 2>&1 | tee "$log"

# Cleanup
util/tidy_dist.py
