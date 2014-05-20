#!/bin/sh

# Make sure __version__.py is current
./setup.py

version=`python -c "from dispcalGUI import meta;print meta.version"`

# Autopackage
mkdir -p dist
makepackage 2>&1 | tee dispcalGUI-$version.dist_autopackage.log
mv "dispcalGUI - Display Calibration $version.package" dist/dispcalGUI-$version.package
mv "dispcalGUI - Display Calibration $version.package.meta" dist/dispcalGUI-$version.package.meta

# Cleanup
util/tidy_dist.py
