if [ `whoami` = "root" ]; then
	prefix=${1:-/usr/local}
	XDG_DATA_DIRS=$prefix/share/:${XDG_DATA_DIRS:-/usr/local/share/:/usr/share/}
else
	prefix=${1:-$HOME/.local}
fi
echo "Uninstalling binary from $prefix/bin..."
rm -f "$prefix/bin/dispcalGUI"
echo "Uninstalling language files from $prefix/share/dispcalGUI/lang..."
rm -f -r "$prefix/share/dispcalGUI/lang"
echo "Uninstalling documentation from $prefix/share/doc/dispcalGUI..."
rm -f -r "$prefix/share/doc/dispcalGUI"
echo "Uninstalling desktop menu entry..."
xdg-desktop-menu uninstall dispcalGUI.desktop
echo "Uninstalling icon resources..."
xdg-icon-resource uninstall --noupdate --size 16 dispcalGUI
xdg-icon-resource uninstall --noupdate --size 22 dispcalGUI
xdg-icon-resource uninstall --noupdate --size 24 dispcalGUI
xdg-icon-resource uninstall --noupdate --size 32 dispcalGUI
xdg-icon-resource uninstall --noupdate --size 48 dispcalGUI
xdg-icon-resource uninstall --noupdate --size 256 dispcalGUI
xdg-icon-resource forceupdate
echo "...done"
