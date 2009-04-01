install_dir=`dirname "$0"`
if [ `whoami` = "root" ]; then
	prefix=${1:-/usr/local}
	XDG_DATA_DIRS=$prefix/share/:${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}
else
	prefix=${1:-$HOME/.local}
fi
mkdir -p "$prefix/bin"
mkdir -p "$prefix/share/dispcalGUI"
echo "Installing dispcalGUI to $prefix/bin..."
if [ -x "$install_dir/dispcalGUI" ]; then
	# binary install
	cp -f "$install_dir/dispcalGUI" "$prefix/bin"
else
	# python install
	echo '#!'$prefix'/bin/python'>"$prefix/bin/dispcalGUI"
	sed -e '1d' "$install_dir/dispcalGUI.py">>"$prefix/bin/dispcalGUI"
	chmod +x "$prefix/bin/dispcalGUI"
	echo "Installing required python modules..."
	cd "$install_dir/RealDisplaySizeMM"
	"$prefix/bin/python" setup.py install --prefix=$prefix
	cd ../demjson
	"$prefix/bin/python" setup.py install --prefix=$prefix
	cd ..
	"$prefix/bin/python" setup_py_dependencies.py install --prefix=$prefix
	echo "Installing presets to $prefix/share/dispcalGUI/presets..."
	cp -f -r "$install_dir/presets" "$prefix/share/dispcalGUI"
	echo "Installing theme files to $prefix/share/dispcalGUI/theme..."
	cp -f -r "$install_dir/theme" "$prefix/share/dispcalGUI"
	echo "Installing testchart files to $prefix/share/dispcalGUI/ti1..."
	cp -f -r "$install_dir/ti1" "$prefix/share/dispcalGUI"
	echo "Installing test.cal to $prefix/share/dispcalGUI..."
	cp -f "$install_dir/test.cal" "$prefix/share/dispcalGUI"
fi
echo "Installing language files to $prefix/share/dispcalGUI/lang..."
cp -f -r "$install_dir/lang" "$prefix/share/dispcalGUI"
echo "Installing documentation to $prefix/share/doc/dispcalGUI..."
mkdir -p "$prefix/share/doc/dispcalGUI/theme/icons"
cp -f -r "$install_dir/LICENSE.txt" "$install_dir/README.html" "$install_dir/screenshots" "$prefix/share/doc/dispcalGUI"
cp -f "$install_dir/theme/header-readme.png" "$prefix/share/doc/dispcalGUI/theme"
cp -f "$install_dir/theme/icons/favicon.ico" "$prefix/share/doc/dispcalGUI/theme/icons"
echo "Installing icon resources..."
xdg-icon-resource install --noupdate --novendor --size 16 "$install_dir/theme/icons/16x16/dispcalGUI.png"
xdg-icon-resource install --noupdate --novendor --size 22 "$install_dir/theme/icons/22x22/dispcalGUI.png"
xdg-icon-resource install --noupdate --novendor --size 24 "$install_dir/theme/icons/24x24/dispcalGUI.png"
xdg-icon-resource install --noupdate --novendor --size 32 "$install_dir/theme/icons/32x32/dispcalGUI.png"
xdg-icon-resource install --noupdate --novendor --size 48 "$install_dir/theme/icons/48x48/dispcalGUI.png"
xdg-icon-resource install --noupdate --novendor --size 256 "$install_dir/theme/icons/256x256/dispcalGUI.png"
xdg-icon-resource forceupdate
echo "Installing desktop menu entry..."
xdg-desktop-menu install --novendor "$install_dir/dispcalGUI.desktop"
echo "...done"
