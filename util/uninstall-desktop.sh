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

echo "Uninstalling desktop menu entry..."
xdg-desktop-menu uninstall "$prefix/share/applications/dispcalGUI.desktop"

echo "Uninstalling icon resources..."
for size in 16 22 24 32 48 256 ; do
	xdg-icon-resource uninstall --noupdate --size $size dispcalGUI
done
xdg-icon-resource forceupdate

echo "...done"
