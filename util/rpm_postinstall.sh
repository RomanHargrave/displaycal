#!/bin/sh

echo "Installing icon resources..."
for size in 16 22 24 32 48 256 ; do
	xdg-icon-resource install --noupdate --novendor --size $size "%{_prefix}/share/dispcalGUI/theme/icons/${size}x${size}/dispcalGUI.png"
done
xdg-icon-resource forceupdate

echo "Installing desktop menu entry..."
xdg-desktop-menu install --novendor "%{_prefix}/share/dispcalGUI/dispcalGUI.desktop"

echo "...done"
