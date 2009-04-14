#!/bin/sh

prefix=
execprefix=

opts=`getopt -o p: --long prefix: -- "$@"`
eval set -- "$opts"
while true ; do
	case "$1" in
		-p|--prefix)
			shift;
			prefix="$1";;
		--exec-prefix)
			shift;
			execprefix="$1";;
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
		XDG_DATA_DIRS="$prefix/share/:${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}"
	else
		prefix="$HOME/.local"
	fi
fi

if [ x"$execprefix" = x"" ]; then
	if [ `whoami` = "root" ]; then
		execprefix="$prefix"
	else
		execprefix="$HOME/bin"
	fi
fi

src_dir=`dirname "$0"`

if [ -e "$src_dir/setup.py" ]; then
	echo "Uninstalling dispcalGUI..."
	"$execprefix/bin/python" "$src_dir/setup.py" uninstall --prefix="$prefix" --exec-prefix="$execprefix"
else
	echo "Removing $execprefix/bin/dispcalGUI..."
	rm -f "$execprefix/bin/dispcalGUI"
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
