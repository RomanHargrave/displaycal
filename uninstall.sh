echo "Uninstalling binary from /usr/local/bin..."
rm -f "/usr/local/bin/dispcalGUI"
echo "Uninstalling language files from /usr/local/share/dispcalGUI/lang..."
rm -f -r "$install_dir/lang" "/usr/local/share/dispcalGUI/lang"
echo "Uninstalling documentation from /usr/local/doc/dispcalGUI..."
rm -f -r "/usr/local/doc/dispcalGUI"
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
