#!/bin/sh

prefix=
scripts=
usedistutils=

opts=`getopt -o p:s:d --long prefix: --long install-scripts: --long use-distutils -- "$@"`
eval set -- "$opts"
while true ; do
	case "$1" in
		-p|--prefix)
			shift;
			prefix="$1";;
		-s|--install-scripts)
			shift;
			scripts="$1";;
		-d|--use-distutils)
			shift;
			usedistutils="--use-distutils";;
		--)
			shift;
			break;;
		*)
			shift;;
	esac
done

if [ x"$prefix" = x"" ]; then
	if [ `whoami` = "root" ]; then
		prefix=/usr/local
	else
		prefix="$HOME/.local"
	fi
fi

if [ `whoami` = "root" ]; then
	XDG_DATA_DIRS="$prefix/share/:${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}"
fi

if [ x"$scripts" = x"" ]; then
	if [ `whoami` = "root" ]; then
		scripts="$prefix/bin"
	else
		scripts="$HOME/bin"
	fi
fi

src_dir=`dirname "$0"`

if [ -e "$src_dir/setup.py" ]; then
	echo "Uninstalling dispcalGUI..."
	"$prefix/bin/python" "$src_dir/setup.py" uninstall --prefix="$prefix" --install-scripts="$scripts" $usedistutils
else
	echo "Removing $prefix/bin/dispcalGUI..."
	rm -f "$prefix/bin/dispcalGUI"
fi

echo "Removing $prefix/share/dispcalGUI..."
rm -f -r "$prefix/share/dispcalGUI"

echo "Removing $prefix/share/doc/dispcalGUI..."
rm -f -r "$prefix/share/doc/dispcalGUI"

echo "Uninstalling desktop menu entry..."
xdg-desktop-menu uninstall "$prefix/share/applications/dispcalGUI.desktop"

echo "Uninstalling icon resources..."
xdg-icon-resource uninstall --noupdate --size 16 dispcalGUI
xdg-icon-resource uninstall --noupdate --size 22 dispcalGUI
xdg-icon-resource uninstall --noupdate --size 24 dispcalGUI
xdg-icon-resource uninstall --noupdate --size 32 dispcalGUI
xdg-icon-resource uninstall --noupdate --size 48 dispcalGUI
xdg-icon-resource uninstall --noupdate --size 256 dispcalGUI
xdg-icon-resource forceupdate

echo "...done"
