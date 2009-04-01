#
# spec file for dispcalGUI (python)
#
Summary: A graphical user interface for the Argyll CMS display calibration utilities
Name: dispcalGUI
Version: 0.2.2b
Release: 1
License: GPL
Group: Applications/Graphics
Source: http://dispcalGUI.hoech.net/dispcalGUI-0.2.2b-src.zip
URL: http://dispcalGUI.hoech.net/
Packager: Florian Höch <dispcalGUI@hoech.net>
Requires: python >= 2.5, python-wxGTK >= 2.8.7
# Requires: python >= 2.5, python-wxGTK >= 2.8.7, xorg-x11-devel, xorg-x11-libX11-devel, xorg-x11-proto-devel

%description
A graphical user interface for the Argyll CMS display calibration utilities.

%prep
%setup -n dispcalGUI-src

%build
cd RealDisplaySizeMM
/usr/bin/python setup.py build_ext
cd ..

%install
chmod +x install.sh
./install.sh /usr

# prepare additional files for README.html
mkdir -p theme-readme/icons
cp theme/header-readme.png theme-readme
cp theme/icons/favicon.ico theme-readme/icons
rm -f -r theme
mv theme-readme theme

%files
/usr/bin/dispcalGUI
%doc LICENSE.txt
%doc README.html
%doc screenshots
%doc theme
/usr/lib/python/site-packages/RealDisplaySizeMM.so
/usr/lib/python/site-packages/argyllRGB2XYZ.py
/usr/lib/python/site-packages/CGATS.py
/usr/lib/python/site-packages/colormath.py
/usr/lib/python/site-packages/demjson.py
/usr/lib/python/site-packages/ICCProfile.py
/usr/lib/python/site-packages/natsort.py
/usr/lib/python/site-packages/pyi_md5pickuphelper.py
/usr/lib/python/site-packages/safe_print.py
/usr/lib/python/site-packages/subprocess26.py
/usr/lib/python/site-packages/tempfile26.py
/usr/lib/python/site-packages/trash.py
/usr/share/dispcalGUI
/usr/share/applications/dispcalGUI.desktop
/usr/share/icons/hicolor/16x16/apps/dispcalGUI.png
/usr/share/icons/hicolor/22x22/apps/dispcalGUI.png
/usr/share/icons/hicolor/24x24/apps/dispcalGUI.png
/usr/share/icons/hicolor/32x32/apps/dispcalGUI.png
/usr/share/icons/hicolor/48x48/apps/dispcalGUI.png
/usr/share/icons/hicolor/256x256/apps/dispcalGUI.png

%post
xdg-icon-resource forceupdate
xdg-desktop-menu forceupdate

%postun
xdg-icon-resource forceupdate
xdg-desktop-menu forceupdate
