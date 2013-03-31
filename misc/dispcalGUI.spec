#
# spec file for package dispcalGUI
#
# Copyright (c) ${YEAR} SUSE LINUX Products GmbH, Nuernberg, Germany.
# Copyright (c) ${YEAR} Florian Hoech
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via http://bugs.opensuse.org/
#


%define numpy_version 1.0
%define py_minversion ${PY_MINVERSION}
%define py_maxversion ${PY_MAXVERSION}
%define wx_minversion ${WX_MINVERSION}

Summary:        ${SUMMARY}
License:        GPL-3.0+
Name:           ${PACKAGE}
Version:        ${VERSION}
Release:        0
Source0:        http://%{name}.hoech.net/download/%{name}-%version.tar.gz
Source1:        copyright
Url:            http://dispcalgui.hoech.net/
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
%if 0%{?mandriva_version} > 0
Group:          Graphics
BuildRequires:  gcc
BuildRequires:  libpython-devel
BuildRequires:  udev
%ifarch x86_64
BuildRequires:  lib64xorg-x11-devel
%else
BuildRequires:  libxorg-x11-devel
%endif
Requires:       argyllcms
Requires:       python-numpy >= %{numpy_version}
Requires:       wxPythonGTK >= %{wx_minversion}
%else
%if 0%{?suse_version} > 0
Group:          Productivity/Graphics/Other
BuildRequires:  gcc
BuildRequires:  python-devel
BuildRequires:  udev
BuildRequires:  update-desktop-files
BuildRequires:  xorg-x11-devel
Requires:       argyllcms
Requires:       python-numpy >= %{numpy_version}
Requires:       python-wxGTK >= %{wx_minversion}
%py_requires
%else
%if 0%{?fedora_version} > 0 || 0%{?rhel_version} > 0 || 0%{?centos_version} > 0
Group:          Applications/Multimedia
BuildRequires:  gcc
BuildRequires:  libX11-devel
BuildRequires:  libXinerama-devel
BuildRequires:  libXrandr-devel
BuildRequires:  libXxf86vm-devel
BuildRequires:  python2-devel
BuildRequires:  udev
Requires:       argyllcms
Requires:       numpy >= %{numpy_version}
Requires:       wxPython >= %{wx_minversion}
%endif
%endif
%endif

%description
${DESC}

%prep
%setup
# Convert line endings in LICENSE.txt
%{__python} -c "f = open('LICENSE.txt', 'rb')
d = f.read().replace('\r\n', '\n').replace('\r', '\n')
f.close()
f = open('LICENSE.txt', 'wb')
f.write(d)
f.close()"

%build
%{__python} setup.py build --use-distutils

%install
install_lib=`%{__python} -c "from distutils.sysconfig import get_python_lib;print get_python_lib(True)"`
%{__python} setup.py install --no-compile --use-distutils \
	--root=$RPM_BUILD_ROOT \
	--prefix=%_prefix \
	--exec-prefix=%_exec_prefix \
	--install-data=%_datadir \
    --install-lib=${install_lib} \
	--skip-instrument-configuration-files \
	--skip-postinstall \
	--record=INSTALLED_FILES
# Strip extensions
bits=`%{__python} -c "import platform;print platform.architecture()[0][:2]"`
python_shortversion=`%{__python} -c "import sys;print ''.join(map(str, sys.version_info[:2]))"`
strip --strip-unneeded ${RPM_BUILD_ROOT}${install_lib}/%{name}/lib${bits}/python${python_shortversion}/*.so
# Byte-compile *.py files and remove traces of RPM_BUILD_ROOT
%if 0%{?mandriva_version} < 201010
# Mandriva 2010.1 got rid of byte-compilation
%{__python} -c "import glob
import os
import platform
import sys
from distutils.sysconfig import get_python_lib
from distutils.util import byte_compile, change_root
bits = platform.architecture()[0][:2]
mod = os.path.join(change_root('$RPM_BUILD_ROOT', get_python_lib(True)), '%{name}')
for py in (glob.glob(os.path.join(mod, '*.py')),
		   glob.glob(os.path.join(mod, 'lib', '*.py')),
		   glob.glob(os.path.join(mod, 'lib', 'agw', '*.py')), 
		   glob.glob(os.path.join(mod, 'lib' + bits, '*.py')), 
		   glob.glob(os.path.join(mod, 'lib' + bits, 'python%s%s' % sys.version_info[:2], '*.py'))):
	byte_compile(py, optimize=0, force=1, prefix='$RPM_BUILD_ROOT')
	if int('0%{?fedora_version}') > 0 or int('0%{?rhel_version}') > 0 or int('0%{?centos_version}') > 0:
		byte_compile(py, optimize=1, force=1, prefix='$RPM_BUILD_ROOT')"
%endif
# Remove doc directory
if [ -e "${RPM_BUILD_ROOT}%_datadir/doc/%{name}-%{version}" ]; then
	rm -rf "${RPM_BUILD_ROOT}%_datadir/doc/%{name}-%{version}"
fi
%if 0%{?suse_version} > 0
# Update desktop files to prevent buildservice from complaining
%suse_update_desktop_file %{name} 2DGraphics
%suse_update_desktop_file "%{buildroot}/etc/xdg/autostart/z-%{name}-apply-profiles.desktop"
%endif
# Remove unused files from list of installed files and add directories
# as well as mark files as executable where needed
%{__python} -c "import os
f = open('INSTALLED_FILES')
paths = [path.replace('$RPM_BUILD_ROOT', '').strip() for path in 
		 filter(lambda path: not '/doc/' in path and not '/etc/' in path and
				not '/man/' in path, 
				f.readlines())]
f.close()
executables = ['argyll_RGB2XYZ.py',
			   'ccmx.py',
			   'colord.py',
			   'colormath.py',
			   'dispcalGUI.py',
			   'encodedstdio.py',
			   'jspacker.py',
			   'main.py',
			   'postinstall.py',
			   'report.py',
			   'safe_print.py',
			   'setup.py',
			   'util_str.py',
			   'util_win.py',
			   'wxDisplayAdjustmentFrame.py',
			   'wxDisplayUniformityFrame.py',
			   'wxLUT3DFrame.py',
			   'wxLUTViewer.py',
			   'wxMeasureFrame.py',
			   'wxProfileInfo.py',
			   'wxTestchartEditor.py',
			   'wxUntetheredFrame.py',
			   'wxwindows.py',
			   'xrandr.py',
			   'Argyll',
			   'dispcalGUI',
			   'dispcalGUI-3DLUT-maker',
			   'dispcalGUI-apply-profiles',
			   'dispcalGUI-profile-info',
			   'dispcalGUI-testchart-editor']
for path in list(paths):
	if path.endswith('.py') and %{?mandriva_version}.0 < 201010:
		# Mandriva 2010.1 got rid of byte-compilation
		paths.append(path + 'c')
		if int('0%{?fedora_version}') > 0 or int('0%{?rhel_version}') > 0 or int('0%{?centos_version}') > 0:
			paths.append(path + 'o')
	if os.path.basename(path) in executables:
		paths.append('%attr(755, root, root) ' + path)
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

%files -f INSTALLED_FILES
%defattr(-,root,root)
%config /etc/xdg/autostart/z-%{name}-apply-profiles.desktop
%doc LICENSE.txt
%doc README.html
%doc screenshots
%doc theme
/usr/share/man/man1/*

%post
${POST}

%postun
${POSTUN}

%changelog
