Summary: Makes software installation on Linux easy
Name: autopackage-devel
Version: 1.4.2
Release: 1
License: GPL
%if 0%{?suse_version} > 0
Group: Development/Tools/Building
BuildRequires: fdupes
%else
%if 0%{?fedora_version} > 0
Group: Development/Tools
%else
%if 0%{?mandriva_version} > 0
Group: Development/Other
%endif
%endif
%endif
Source: http://autopackage.googlecode.com/files/autopackage-devel-1.4.2.tar.bz2
URL: http://autopackage.org/
#!BuildIgnore: post-build-checks
BuildRoot: %{_tmppath}/%{name}-%{version}-root
BuildRequires: autopackage, gcc, gcc-c++
Autoreq: 0
Requires: autopackage, gcc, gcc-c++

%description
Software distributed using Autopackage can be installed on multiple Linux 
distributions and integrate well into the desktop environment.

%prep
%setup -n autopackage

%build

%install
export PATH=`pwd`/apbuild:$PATH
make install PREFIX=%{buildroot}/usr
%if 0%{?suse_version} > 0
%fdupes -s $RPM_BUILD_ROOT/usr/gtk-headers
%endif
export NO_BRP_CHECK_RPATH=true

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
/usr/bin/*
/usr/binreloc/*
/usr/gtk-headers/*
/usr/include/apbuild/*
/usr/libexec/autopackage/*
/usr/share/aclocal/*
/usr/share/apbuild/*
/usr/share/autopackage/*
%dir /usr/binreloc
%dir /usr/gtk-headers
%dir /usr/include/apbuild
%dir /usr/libexec/autopackage
%dir /usr/share/aclocal
%dir /usr/share/apbuild

%changelog
* Tue Aug 03 2010 Florian Höch <florian.hoech@gmx.de>
- Version 1.4.2
