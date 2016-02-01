#!/bin/sh

# Make sure __version__.py is current
./setup.py

version=`python -c "from DisplayCAL import meta;print meta.version"`

# Autopackage
mkdir -p dist
makepackage 2>&1 | tee DisplayCAL-$version.dist_autopackage.log
mv "DisplayCAL - Display Calibration $version.package" dist/DisplayCAL-$version.package
mv "DisplayCAL - Display Calibration $version.package.meta" dist/DisplayCAL-$version.package.meta

# Cleanup
util/tidy_dist.py
