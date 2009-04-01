if [ `whoami` = "root" ]; then
	prefix=${1:-/usr/local}
	XDG_DATA_DIRS=$prefix/share/:${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}
else
	prefix=${1:-$HOME/.local}
fi
echo "Uninstalling binary from $prefix/bin..."
rm -f "$prefix/bin/dispcalGUI"
if [ ! -x "$install_dir/dispcalGUI" ]; then
	# python install
	echo "Uninstalling python modules from $prefix/lib/python/site-packages..."
	rm -f "$prefix/lib/python/site-packages/RealDisplaySizeMM.so"
	rm -f "$prefix/lib/python/site-packages/argyllRGB2XYZ.py"*
	rm -f "$prefix/lib/python/site-packages/CGATS.py"*
	rm -f "$prefix/lib/python/site-packages/colormath.py"*
	rm -f "$prefix/lib/python/site-packages/demjson.py"*
	rm -f "$prefix/lib/python/site-packages/ICCProfile.py"*
	rm -f "$prefix/lib/python/site-packages/natsort.py"*
	rm -f "$prefix/lib/python/site-packages/pyi_md5pickuphelper.py"*
	rm -f "$prefix/lib/python/site-packages/safe_print.py"*
	rm -f "$prefix/lib/python/site-packages/subprocess26.py"*
	rm -f "$prefix/lib/python/site-packages/tempfile26.py"*
	rm -f "$prefix/lib/python/site-packages/trash.py"*
	rm -f "$prefix/lib/python/site-packages/RealDisplaySizeMM-"*.egg-info
	rm -f "$prefix/lib/python/site-packages/demjson-"*.egg-info
	rm -f "$prefix/lib/python/site-packages/dispcalGUI_py_dependencies-"*.egg-info
fi
echo "Uninstalling files from $prefix/share/dispcalGUI..."
rm -f -r "$prefix/share/dispcalGUI"
echo "Uninstalling documentation from $prefix/share/doc/dispcalGUI..."
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
