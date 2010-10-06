%define numpy_version 1.0
%define py_minversion ${PY_MINVERSION}
%define py_maxversion ${PY_MAXVERSION}
%define wx_minversion ${WX_MINVERSION}
Summary: ${SUMMARY}
Name: ${PACKAGE}
Version: ${VERSION}
Release: 1
License: GPL
Source: http://%{name}.hoech.net/%{name}-%version.tar.gz
URL: http://dispcalgui.hoech.net/
BuildArchitectures: noarch
BuildRoot: %{_tmppath}/%{name}-%{version}-root
BuildRequires: autopackage-devel, python >= %{py_minversion}, python <= %{py_maxversion}
%if 0%{?mandriva_version} > 0
Group: Graphics
Requires: autopackage, python >= %{py_minversion}, python <= %{py_maxversion}, wxPythonGTK >= %{wx_minversion}, python-numpy >= %{numpy_version}
%else
%if 0%{?suse_version} > 0
Group: Productivity/Graphics/Other
Requires: autopackage, python >= %{py_minversion}, python <= %{py_maxversion}, python-wxGTK >= %{wx_minversion}, python-numpy >= %{numpy_version}
%py_requires
%else
%if 0%{?fedora_version} > 0
Group: Applications/Multimedia
Requires: autopackage, python >= %{py_minversion}, python <= %{py_maxversion}, wxPython >= %{wx_minversion}, numpy >= %{numpy_version}
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
chmod +x dist/dispcalGUI-*.package

%install
mkdir -p %{buildroot}/var/lib/packages
mv dist/dispcalGUI-*.package %{buildroot}/var/lib/packages
mv dist/dispcalGUI-*.package.meta %{buildroot}/var/lib/packages

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
/var/lib/packages/dispcalGUI-*.package
/var/lib/packages/dispcalGUI-*.package.meta

%changelog
* ${DATE} ${MAINTAINER} <${MAINTAINER_EMAIL}>
- Version ${VERSION}
