#!/bin/sh

version=`python -c "from dispcalGUI import meta;print meta.version"`

# Autopackage
makepackage 2>&1 | tee dispcalGUI-$version.dist_autopackage.log
mv "dispcalGUI - Display Calibration $version.package" dist/dispcalGUI-$version.package
mv "dispcalGUI - Display Calibration $version.package.meta" dist/dispcalGUI-$version.package.meta

