Summary: Makes software installation on Linux easy
Name: autopackage
Version: 1.4.2
Release: 1
License: GPL
%if 0%{?suse_version} > 0
Group: Development/Tools/Building
%else
%if 0%{?fedora_version} > 0
Group: Development/Tools
%else
%if 0%{?mandriva_version} > 0
Group: Development/Other
%endif
%endif
%endif
Source: http://autopackage.googlecode.com/files/autopackage-1.4.2-x86.tar.bz2
URL: http://autopackage.org/
#!BuildIgnore: post-build-checks
BuildRoot: %{_tmppath}/%{name}-%{version}-root
BuildRequires: gcc, libstdc++
Autoreqprov: 0
Requires: tcl
Provides: autopackage

%description
Software distributed using Autopackage can be installed on multiple Linux 
distributions and integrate well into the desktop environment.

%prep
%setup -n %{name}

%build

%install
#!/bin/bash
# Install script for Autopackage Support Code

###
#
# This code is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Copyright 2002-2003 Curtis Knight (knighcl@fastmail.fm)
#
###

##########
###
### Determine directories
###
##########

prefix=%{buildroot}/usr

etc_dir=%{buildroot}/etc

##########
###
### Install
###
##########

mkdir -p "$prefix/bin"
mkdir -p "$prefix/libexec/autopackage"
mkdir -p "$prefix/share/autopackage"
mkdir -p "$etc_dir/autopackage"

set +e
cp -f "package"               "$prefix/bin/package"
cp -f "autopackage"           "$prefix/bin/autopackage"
cp -f "libexec"/*             "$prefix/libexec/autopackage/"
cp -f "share"/apkg-*          "$prefix/share/autopackage/"
cp -f "share"/*template       "$prefix/share/autopackage/"
cp -fr "share/locale"         "$prefix/share/"
cp -f "share/remove"          "$prefix/share/autopackage/"
# FIXME: should NOT be commented - this is done so that some return code does not fail
# the install and stop the auto-setup code before gtkfe can be installed.
#set -e

# sub in autopackage prefix into config file
sed "s|%AutopackagePrefix%|/usr|g" "etc/config" >"$etc_dir/autopackage/config"

export NO_BRP_CHECK_RPATH=true
%find_lang %{name}

%clean
rm -rf $RPM_BUILD_ROOT

%post
#!/bin/bash

prefix=/usr

pushd "$prefix/libexec/autopackage" >/dev/null
[ ! -e libuau.so.3 ] && ln -s libuau.so.3.0.0 libuau.so.3
[ ! -e libcurl.so.2 ] && ln -s libcurl.so.2.0.2 libcurl.so.2
popd >/dev/null

# if we have write access to the linker cache, refresh it (ie if we are root)
if [ -w /etc/ld.so.cache ]; then
    echo -n "Refreshing linker cache, please wait ... "
    /sbin/ldconfig
    echo "done"
fi

_refresh_again=false

# install libgcc_s.so.1 if needed
if ! /sbin/ldconfig -p | grep -q libgcc_s.so.1 && [ ! -e "$prefix/lib/libgcc_s.so.1" ]; then
    echo "Your system is missing the GCC support library, putting a copy in $prefix/lib"
    mkdir -p "$prefix/lib"
    cp "$prefix/libexec/autopackage/libgcc_s.so.1" "$prefix/lib/libgcc_s.so.1"
    _refresh_again=true
fi

if ! /sbin/ldconfig -p | grep -q libstdc++.so.5 && [ ! -e "$prefix/lib/libstdc++.so.5" ]; then
    echo "Your system is missing v5 of the C++ support library, putting a copy in $prefix/lib"
    mkdir -p "$prefix/lib"
    cp "$prefix/libexec/autopackage/libstdc++.so.5.0.7" "$prefix/lib/libstdc++.so.5.0.7.apkg"
    ln -s "$prefix/lib/libstdc++.so.5.0.7.apkg" "$prefix/lib/libstdc++.so.5"
    _refresh_again=true
fi

if ! /sbin/ldconfig -p | grep -q libstdc++.so.6 && [ ! -e "$prefix/lib/libstdc++.so.6" ]; then
    echo "Your system is missing v6 of the C++ support library, putting a copy in $prefix/lib"
    mkdir -p "$prefix/lib"
    cp "$prefix/libexec/autopackage/libstdc++.so.6.0.9" "$prefix/lib/libstdc++.so.6.0.9.apkg"
    ln -s "$prefix/lib/libstdc++.so.6.0.9.apkg" "$prefix/lib/libstdc++.so.6"
    _refresh_again=true
fi

if $_refresh_again && [ -w /etc/ld.so.cache ]; then
    echo -n "Refreshing linker cache again, please wait ... "
    /sbin/ldconfig
    echo "done"
fi

# load installed autopackage support code
[ -e /etc/autopackage/config ] && source /etc/autopackage/config;

# link to autopackage functions - required for upgrading installation session
if [ -e "$autopackage_prefix/share/autopackage/apkg-funclib" ]; then
	export PATH=$autopackage_prefix/share/autopackage:$PATH
    source "$autopackage_prefix/share/autopackage/apkg-funclib"
fi

# add marker file to denote that this is a first time installation session
# of the support code; _initializeAutopackage converts this to variable
# _autopackage_support_install=1
touch "$WORKING_DIRECTORY/apkg-support-install"

# initialize autopackage variables (cpu_architecture)
_initializeAutopackage

# install GTK+ graphical front end
# set variable to install in same location as support code
export first_autosu="true"
_installGTKFE
r="$?"

# unset variable to ask user where to install selected packages
unset first_autosu

# return value in case GTK+ graphical front end fails
if [[ "$r" != "0" ]]; then
    exit 5
fi

# add to PATH if necessary
if ! isInList "$prefix/bin" "$PREFIX"; then
    updateEnv PATH "$prefix/bin"
    shell=$(basename $(cat /etc/passwd | grep ^$(whoami): | awk -F: '{print $7}'))
    if [[ "$shell" == "" ]]; then
        shell=$(basename $(readlink /bin/sh 2> /dev/null))
        [[ "$shell" == "" ]] && shell="bash" # Still empty? Then use bash as a fallback
    fi
    out "Please run 'exec %s' in each terminal to update your path." "$shell";
    out " "
fi


### DONE
"$autopackage_silent" || echo
exit 0

%preun
#!/bin/bash

prefix=/usr

pushd "$prefix/libexec/autopackage" >/dev/null
rm libuau.so.3
rm libcurl.so.2
popd >/dev/null

exit 0

%files -f %{name}.lang
%defattr(-,root,root)
/usr/bin/package
/usr/bin/autopackage
%config /etc/autopackage/config
/usr/libexec/autopackage/*
/usr/share/autopackage/*
%dir /etc/autopackage/
%dir /usr/libexec/autopackage/
%dir /usr/share/autopackage/

%changelog
* Tue Aug 03 2010 Florian Höch <florian.hoech@gmx.de>
- Version 1.4.2
