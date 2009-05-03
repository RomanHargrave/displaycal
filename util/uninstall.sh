#!/bin/sh

if [ `whoami` = "root" ]; then
	prefix=/usr/local
else
	prefix="$HOME/.local"
fi

python="/usr/bin/env python"

opts=`getopt --long prefix: --long python: --long install-scripts: --long use-distutils -- "$0" "$@"`
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
		--)
			shift;
			break;;
		*)
			opts="$opts$1 ";
			shift;;
	esac
done

if [ `whoami` = "root" ]; then
	XDG_DATA_DIRS="$prefix/share/:${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}"
fi

src_dir=`dirname "$0"`

if [ -e "$src_dir/setup.py" ]; then
	$python "$src_dir/setup.py" uninstall --prefix="$prefix" $opts
else
	echo "Removing $prefix/bin/dispcalGUI..."
	rm -f "$prefix/bin/dispcalGUI"

	echo "Removing $prefix/share/doc/dispcalGUI..."
	rm -f -r "$prefix/share/doc/dispcalGUI"

	echo "Uninstalling desktop menu entry..."
	xdg-desktop-menu uninstall "$prefix/share/applications/dispcalGUI.desktop"

	echo "Uninstalling icon resources..."
	for size in 16 22 24 32 48 256 ; do
		xdg-icon-resource uninstall --noupdate --size $size dispcalGUI
	done
	xdg-icon-resource forceupdate
fi

echo "...done"
