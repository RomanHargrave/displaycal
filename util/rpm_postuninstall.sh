#!/bin/sh

# Remove udev rules or hotplug scripts symlinks
for file in "/etc/udev/rules.d/55-Argyll.rules" "/etc/udev/rules.d/45-Argyll.rules" "/etc/hotplug/usb/Argyll" "/etc/hotplug/usb/Argyll.usermap" ; do
	if [ ! -e $file ]; then
		if [ -L $file ]; then
			rm -f $file
		fi
	fi
done

# Update icon cache and menu
which xdg-desktop-menu > /dev/null 2>&1 && xdg-desktop-menu forceupdate || true
which xdg-icon-resource > /dev/null 2>&1 && xdg-icon-resource forceupdate || true
