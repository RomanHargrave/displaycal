#!/bin/sh

# Make sure __version__.py is current
./setup.py

appname=`python -c "from DisplayCAL import meta;print meta.name"`
version=`python -c "from DisplayCAL import meta;print meta.version"`

# OpenSUSE build service
pushd ../obs/multimedia:color_management/DisplayCAL
osc update
osc service localrun
for filename in *.tar.gz ; do
	echo "$filename" | grep "^$appname-" > /dev/null && (
		echo "$filename" | grep "^$appname-$version" > /dev/null || (
			osc remove $filename
		)
	)
done
for filename in *.tar.gz.1 ; do
	osc remove --force $filename
done
osc remove --force DisplayCAL.dsc
osc remove --force PKGBUILD
osc addremove
osc ci -m "Update to version $version"
popd
