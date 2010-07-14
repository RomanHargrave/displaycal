%define numpy_version 1.0
%define py_minversion ${PY_MINVERSION}
%define py_maxversion ${PY_MAXVERSION}
%define wx_minversion ${WX_MINVERSION}
Summary: ${DESC}
Name: ${PACKAGE}
Version: ${VERSION}
Release: 1
License: GPL
Group: Applications/Graphics
Source: http://%{name}.hoech.net/%{name}-%version.tar.gz
URL: http://dispcalgui.hoech.net/
BuildRoot: %{_tmppath}/%{name}-%{version}-root
%if 0%{?mandriva_version} > 0
%ifarch x86_64
BuildRequires: udev, gcc, python >= %{py_minversion}, python <= %{py_maxversion}, libpython-devel, lib64xorg-x11-devel
%else
BuildRequires: udev, gcc, python >= %{py_minversion}, python <= %{py_maxversion}, libpython-devel, libxorg-x11-devel
%endif
Requires: python >= %{py_minversion}, python <= %{py_maxversion}, wxPythonGTK >= %{wx_minversion}, python-numpy >= %{numpy_version}
%else
%if 0%{?debian_version} > 0
BuildRequires: udev, gcc, python >= %{py_minversion}, python <= %{py_maxversion}, python-all-dev, libxinerama-dev, libxrandr-dev, libxxf86vm-dev
Requires: python >= %{py_minversion}, python <= %{py_maxversion}, python-wxgtk2.8 >= %{wx_minversion}, python-numpy >= %{numpy_version}
%else
%if 0%{?suse_version} > 0
BuildRequires: udev, update-desktop-files, gcc, python >= %{py_minversion}, python <= %{py_maxversion}, python-devel, xorg-x11-devel
Requires: python >= %{py_minversion}, python <= %{py_maxversion}, python-wxGTK >= %{wx_minversion}, python-numpy >= %{numpy_version}
%else
%if 0%{?fedora_version} > 0
BuildRequires: udev, gcc, python >= %{py_minversion}, python <= %{py_maxversion}, python-devel, libX11-devel, libXinerama-devel, libXrandr-devel, libXxf86vm-devel
Requires: python >= %{py_minversion}, python <= %{py_maxversion}, wxPython >= %{wx_minversion}, numpy >= %{numpy_version}
%endif
%endif
%endif
%endif

%description
Calibrates and characterizes display devices using a hardware sensor. Supports
multiple displays and a variety of available settings like customizable
whitepoint, luminance, black level, and tone response curve as well as the
creation of matrix and look-up-table ICC profiles with optional gamut mapping.
Calibrations and profiles can be verified through measurements, and profiles 
can be installed to setup the X server for colormanagement-aware applications.
Powered by the open source colormanagement system Argyll CMS.

%prep
%setup

%build
# handled by install

%install
# Make files executable
chmod +x "scripts/%{name}"
chmod +x "misc/Argyll"
# Convert line endings in LICENSE.txt
python -c "f = open('LICENSE.txt', 'rb')
d = f.read().replace('\r\n', '\n').replace('\r', '\n')
f.close()
f = open('LICENSE.txt', 'wb')
f.write(d)
f.close()"
# Install
%if 0%{?fedora_version} > 0
export PYO=-O1
%endif
python`python -c "import sys;print sys.version[:3]"` setup.py install $PYO --use-distutils \
	--prefix=$RPM_BUILD_ROOT%_prefix \
	--exec-prefix=$RPM_BUILD_ROOT%_exec_prefix \
	--install-data=$RPM_BUILD_ROOT%_datadir \
	--skip-instrument-configuration-files --record=INSTALLED_FILES
# Remove doc directory
if [ -e "${RPM_BUILD_ROOT}%_datadir/doc/%{name}-%{version}" ]; then
	rm -rf "${RPM_BUILD_ROOT}%_datadir/doc/%{name}-%{version}"
fi
# udev/hotplug
mkdir -p "${RPM_BUILD_ROOT}/usr/share/dispcalGUI/usb"
# USB and serial instruments using udev, where udev already creates /dev/bus/usb/00X/00X devices
cp -f "misc/92-Argyll.rules" "${RPM_BUILD_ROOT}/usr/share/dispcalGUI/usb/92-Argyll.rules"
echo "/usr/share/dispcalGUI/usb/92-Argyll.rules">>INSTALLED_FILES
# USB using udev, where there are NOT /dev/bus/usb/00X/00X devices
cp -f  "misc/45-Argyll.rules" "${RPM_BUILD_ROOT}/usr/share/dispcalGUI/usb/45-Argyll.rules"
echo "/usr/share/dispcalGUI/usb/45-Argyll.rules">>INSTALLED_FILES
# USB using hotplug and Serial using udev (older versions of Linux)
cp -f "misc/Argyll" "${RPM_BUILD_ROOT}/usr/share/dispcalGUI/usb/Argyll"
echo "/usr/share/dispcalGUI/usb/Argyll">>INSTALLED_FILES
cp -f "misc/Argyll.usermap" "${RPM_BUILD_ROOT}/usr/share/dispcalGUI/usb/Argyll.usermap"
echo "/usr/share/dispcalGUI/usb/Argyll.usermap">>INSTALLED_FILES
%if 0%{?suse_version} > 0
# Update categories to prevent buildservice from complaining
%suse_update_desktop_file %{name} 2DGraphics
%endif
# Remove unused files from list of installed files and add directories
python -c "import os
f = open('INSTALLED_FILES')
paths = [path.replace('$RPM_BUILD_ROOT', '').strip() for path in 
		 filter(lambda path: not '/doc/' in path, f.readlines())]
f.close()
for path in list(paths):
	while True:
		path = os.path.dirname(path)
		if os.path.isdir(path):
			break
		else:
			directory = '%dir ' + path
			if not directory in paths:
				paths.append(directory)
f = open('INSTALLED_FILES', 'w')
f.write('\n'.join(paths))
f.close()"

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)
%doc LICENSE.txt
%doc README.html
%doc screenshots
%doc theme

%post
if [ -e "/etc/udev/rules.d" ]; then
	ls /dev/bus/usb/*/* > /dev/null 2>&1 && (
		# USB and serial instruments using udev, where udev already creates /dev/bus/usb/00X/00X devices
		if [ ! -e "/etc/udev/rules.d/55-Argyll.rules" ]; then
			cp "/usr/share/dispcalGUI/usb/92-Argyll.rules" "/etc/udev/rules.d/55-Argyll.rules"
		fi
	) || (
		# USB using udev, where there are NOT /dev/bus/usb/00X/00X devices
		if [ ! -e "/etc/udev/rules.d/45-Argyll.rules" ]; then
			cp "/usr/share/dispcalGUI/usb/45-Argyll.rules" "/etc/udev/rules.d/45-Argyll.rules"
		fi
	)
else
	if [ -e "/etc/hotplug"]; then
		# USB using hotplug and Serial using udev (older versions of Linux)
		if [ ! -e "/etc/hotplug/usb/Argyll" ]; then
			cp "/usr/share/dispcalGUI/usb/Argyll" "/etc/hotplug/usb/Argyll"
		fi
		if [ ! -e "/etc/hotplug/usb/Argyll.usermap" ]; then
			cp "/usr/share/dispcalGUI/usb/Argyll.usermap" "/etc/hotplug/usb/Argyll.usermap"
		fi
	fi
fi
which xdg-icon-resource > /dev/null 2>&1 && xdg-icon-resource forceupdate || true
which xdg-desktop-menu > /dev/null 2>&1 && xdg-desktop-menu forceupdate || true

%postun
which xdg-desktop-menu > /dev/null 2>&1 && xdg-desktop-menu forceupdate || true
which xdg-icon-resource > /dev/null 2>&1 && xdg-icon-resource forceupdate || true

%changelog
* ${DATE} ${MAINTAINER} <${MAINTAINER_EMAIL}>
- Version ${VERSION}
