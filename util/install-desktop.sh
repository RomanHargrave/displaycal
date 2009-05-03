#!/bin/sh

if [ `whoami` = "root" ]; then
	prefix=/usr/local
else
	prefix="$HOME/.local"
fi

opts=`getopt --long prefix: -- "$0" "$@"`
eval set -- "$opts"
while true ; do
	case "$1" in
		--prefix)
			shift;
			prefix="$1";
			shift;;
		--)
			shift;
			break;;
		*)
			shift;;
	esac
done

if [ `whoami` = "root" ]; then
	XDG_DATA_DIRS="$prefix/share/:${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}"
fi

echo "Installing icon resources..."
for size in 16 22 24 32 48 256 ; do
	xdg-icon-resource install --noupdate --novendor --size $size "$prefix/share/dispcalGUI/theme/icons/${size}x${size}/dispcalGUI.png"
done
xdg-icon-resource forceupdate

echo "Installing desktop menu entry..."
xdg-desktop-menu install --novendor "$prefix/share/dispcalGUI/dispcalGUI.desktop"

echo "...done"
