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
	echo "Installing dispcalGUI..."
	$python "$src_dir/setup.py" install --prefix="$prefix" --install-scripts="$scripts" $opts
else
	echo "Installing dispcalGUI to $prefix/bin..."
	mkdir -p "$prefix/bin"
	cp -f "$src_dir/dispcalGUI" "$prefix/bin"
	
	echo "Installing language files to $prefix/share/dispcalGUI/lang..."
	mkdir -p "$prefix/share/dispcalGUI"
	cp -f -r "$src_dir/lang" "$prefix/share/dispcalGUI"
fi

echo "Installing documentation to $prefix/share/doc/dispcalGUI..."
mkdir -p "$prefix/share/doc/dispcalGUI/theme/icons"
cp -f -r "$src_dir/LICENSE.txt" "$src_dir/README.html" "$src_dir/screenshots" "$prefix/share/doc/dispcalGUI"
cp -f "$src_dir/theme/header-readme.png" "$prefix/share/doc/dispcalGUI/theme"
cp -f "$src_dir/theme/icons/favicon.ico" "$prefix/share/doc/dispcalGUI/theme/icons"

echo "Installing icon resources..."
xdg-icon-resource install --noupdate --novendor --size 16 "$src_dir/theme/icons/16x16/dispcalGUI.png"
xdg-icon-resource install --noupdate --novendor --size 22 "$src_dir/theme/icons/22x22/dispcalGUI.png"
xdg-icon-resource install --noupdate --novendor --size 24 "$src_dir/theme/icons/24x24/dispcalGUI.png"
xdg-icon-resource install --noupdate --novendor --size 32 "$src_dir/theme/icons/32x32/dispcalGUI.png"
xdg-icon-resource install --noupdate --novendor --size 48 "$src_dir/theme/icons/48x48/dispcalGUI.png"
xdg-icon-resource install --noupdate --novendor --size 256 "$src_dir/theme/icons/256x256/dispcalGUI.png"
xdg-icon-resource forceupdate

echo "Installing desktop menu entry..."
xdg-desktop-menu install --novendor "$src_dir/dispcalGUI.desktop"

echo "...done"
