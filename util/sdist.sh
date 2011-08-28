#!/bin/sh

version=`python -c "from dispcalGUI import meta;print meta.version"`

# Source tarball
./setup.py sdist --use-distutils 2>&1 | tee dispcalGUI-$version.sdist.log

# 0install feed
which 0publish > /dev/null && (
	echo "Updating 0install feed..."
	0publish --add-version=$version \
--archive-url=http://dispcalgui.hoech.net/archive/$version/dispcalGUI-$version.tar.gz \
--archive-file=dist/dispcalGUI-$version.tar.gz \
--set-main="dispcalGUI-$version/dispcalGUI.pyw" \
--set-released="`python -c "import os,time;print time.strftime('%Y-%m-%d', time.localtime(os.stat('dist/dispcalGUI-$version.tar.gz').st_mtime))"`" \
--set-stability=stable -x \
dist/0install/dispcalGUI.xml
)
