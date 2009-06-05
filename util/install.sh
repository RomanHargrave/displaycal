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
	$python "$src_dir/setup.py" install --prefix="$prefix" $opts
else
	if [ `whoami` = "root" ]; then
		echo "Installing measurement device configuration files..."
		if [ -e "/usr/share/PolicyKit/policy" ] && [ -e "/usr/share/hal/fdi/policy/10osvendor" ]; then
			# USB and Serial access using PolicyKit V0.6 + HAL (recent versions of Linux)
			cp -u "misc/color-device-file.policy" "/usr/share/PolicyKit/policy/color-device-file.policy"
			cp -u "misc/19-color.fdi" "/usr/share/hal/fdi/policy/10osvendor/19-color.fdi"
		fi
		if [ -e "/etc/udev/rules.d" ]; then
			ls /dev/bus/usb/*/* > /dev/null 2>&1 && (
				# USB and serial instruments using udev, where udev already creates /dev/bus/usb/00X/00X devices
				cp -u "misc/55-Argyll.rules" "/etc/udev/rules.d/55-Argyll.rules"
			) || (
				# USB using udev, where there are NOT /dev/bus/usb/00X/00X devices
				cp -u "misc/45-Argyll.rules" "/etc/udev/rules.d/45-Argyll.rules"
			)
		else
			if [ -e "/etc/hotplug"]; then
				# USB using hotplug and Serial using udev (older versions of Linux)
				mkdir -p "/etc/hotplug/usb/"
				cp -u "misc/Argyll" "/etc/hotplug/usb/Argyll"
				cp -u "misc/Argyll.usermap" "/etc/hotplug/usb/Argyll.usermap"
			fi
			if [ -e "/etc/udev/permissions.d" ]; then
				# Serial instruments using udev (older versions of Linux)
				cp -u "misc/10-Argyll.permissions" "/etc/udev/permissions.d/10-Argyll.permissions"
			fi
		fi
	fi

	echo "Installing dispcalGUI to $prefix/bin..."
	mkdir -p "$prefix/bin"
	cp -f "$src_dir/dispcalGUI" "$prefix/bin"

	echo "Installing documentation to $prefix/share/doc/dispcalGUI..."
	mkdir -p "$prefix/share/doc/dispcalGUI/theme/icons"
	cp -f -r "$src_dir/LICENSE.txt" "$src_dir/README.html" "$src_dir/screenshots" "$prefix/share/doc/dispcalGUI"
	cp -f "$src_dir/theme/header-readme.png" "$prefix/share/doc/dispcalGUI/theme"
	cp -f "$src_dir/theme/icons/favicon.ico" "$prefix/share/doc/dispcalGUI/theme/icons"

	echo "Installing icon resources..."
	for size in 16 22 24 32 48 256 ; do
		xdg-icon-resource install --noupdate --novendor --size $size "$src_dir/theme/icons/${size}x${size}/dispcalGUI.png"
	done
	xdg-icon-resource forceupdate

	echo "Installing desktop menu entry..."
	xdg-desktop-menu install --novendor "$src_dir/dispcalGUI.desktop"
fi

echo "...done"
