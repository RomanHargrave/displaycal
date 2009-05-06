#!/bin/sh

echo "Uninstalling desktop menu entry..."
xdg-desktop-menu uninstall "%{_prefix}/share/applications/dispcalGUI.desktop"

echo "Uninstalling icon resources..."
for size in 16 22 24 32 48 256 ; do
	xdg-icon-resource uninstall --noupdate --size $size dispcalGUI
done
xdg-icon-resource forceupdate

echo "...done"
