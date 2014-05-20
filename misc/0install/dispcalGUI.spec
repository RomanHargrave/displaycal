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
Url:            ${URL}
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
BuildArch:      noarch
BuildRequires:  python
BuildRequires:  xdg-utils
Requires:       xdg-utils
%if 0%{?mandriva_version} > 0
Group:          Graphics
Requires:       python-numpy >= %{numpy_version}
Requires:       wxPythonGTK >= %{wx_minversion}
Requires:       zeroinstall-injector
%else
%if 0%{?suse_version} > 0
Group:          Productivity/Graphics/Other
BuildRequires:  update-desktop-files
BuildRequires:  zeroinstall-injector
Requires:       python-numpy >= %{numpy_version}
Requires:       python-wxGTK >= %{wx_minversion}
Requires:       zeroinstall-injector
%py_requires
%else
%if 0%{?fedora_version} > 0 || 0%{?rhel_version} > 0 || 0%{?centos_version} > 0
Group:          Applications/Multimedia
Requires:       numpy >= %{numpy_version}
Requires:       wxPython >= %{wx_minversion}
Requires:       0install
%endif
%endif
%endif

%description
${DESC}

%prep
%setup

%build

%install
PYTHONPATH=. %{__python} util/0install_desktop.py "%{buildroot}%{_datadir}"

%if 0%{?suse_version} > 0
	# Update desktop files to prevent buildservice from complaining
	desktopfilenames=`%{__python} -c "import glob
import os
print ' '.join([os.path.splitext(os.path.basename(path))[0] for path in
				glob.glob('%{buildroot}%{_datadir}/applications/*.desktop')])"`
	for desktopfilename in $desktopfilenames ; do
		%suse_update_desktop_file $desktopfilename 2DGraphics
	done
%endif

%files
%defattr(-,root,root)
/usr/share/applications/*.desktop
/usr/share/icons/hicolor/*/apps/*.png

%post
${POST}

%postun
${POSTUN}

%changelog
