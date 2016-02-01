#
# spec file for package DisplayCAL
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
Group:          Applications/Multimedia
Name:           ${PACKAGE}
Version:        ${VERSION}
Release:        0
Source:         ${URL}download/%{name}-%version.tar.gz
Url:            ${URL}
BuildArch:      noarch
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
BuildRequires:  autopackage-devel
BuildRequires:  python < 3.0
BuildRequires:  python >= %{py_minversion}
%if 0%{?mandriva_version} > 0
Requires:       autopackage
Requires:       python < 3.0
Requires:       python >= %{py_minversion}
Requires:       python-numpy >= %{numpy_version}
Requires:       wxPythonGTK >= %{wx_minversion}
%else
%if 0%{?suse_version} > 0
Requires:       autopackage
Requires:       python < 3.0
Requires:       python >= %{py_minversion}
Requires:       python-numpy >= %{numpy_version}
Requires:       python-wxGTK >= %{wx_minversion}
%py_requires
%else
%if 0%{?fedora_version} > 0
Requires:       autopackage
Requires:       numpy >= %{numpy_version}
Requires:       python < 3.0
Requires:       python >= %{py_minversion}
Requires:       wxPython >= %{wx_minversion}
%endif
%endif
%endif

%description
${DESC}

%prep
%setup
# Make files executable
chmod +x misc/Argyll
chmod +x scripts/*
chmod +x util/*.sh
# Convert line endings in LICENSE.txt
python -c "f = open('LICENSE.txt', 'rb')
d = f.read().replace('\r\n', '\n').replace('\r', '\n')
f.close()
f = open('LICENSE.txt', 'wb')
f.write(d)
f.close()"

%build
util/dist_autopackage.sh
chmod +x dist/${APPNAME}-*.package

%install
mkdir -p %{buildroot}/var/lib/packages
mv dist/${APPNAME}-*.package %{buildroot}/var/lib/packages
mv dist/${APPNAME}-*.package.meta %{buildroot}/var/lib/packages

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
/var/lib/packages/${APPNAME}-*.package
/var/lib/packages/${APPNAME}-*.package.meta

%changelog
