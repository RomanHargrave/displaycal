#!/bin/sh

prefix=
python="/usr/bin/env python"
scripts=

opts=`getopt --long prefix: --long python: --long install-scripts: --long install-data: --long use-distutils -- "$0" "$@"`
eval set -- "$opts"
opts=
while true ; do
	case "$1" in
		--prefix)
			shift;
			prefix="$1";
			shift;;
		--python)
			shift;
			python="$1";
			shift;;
		--install-scripts)
			shift;
			scripts="$1";
			shift;;
		--install-data)
			opts="$opts$1";
			shift;
			opts="$opts=\"$1\" ";
			shift;;
		--)
			shift;
			break;;
		*)
			opts="$opts$1 ";
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
	$python "$src_dir/setup.py" uninstall --prefix="$prefix" --install-scripts="$scripts" $opts
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
