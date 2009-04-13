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
Requires: python >= 2.5, python < 3.0, python-wxGTK >= 2.8.7

%description
A graphical user interface for the Argyll CMS display calibration utilities.

%prep
%setup -n dispcalGUI-src

%build
/usr/bin/python setup.py build

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
/usr/lib/python/site-packages/dispcalGUI*
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
