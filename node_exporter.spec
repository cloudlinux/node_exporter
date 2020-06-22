Autoreq: 0
%define _clshare_plus /usr/share/cloudlinux/cl_plus

Name: node-exporter
Version: 1.0.1
Release: 1%{dist}.cloudlinux
Summary: Node Exporter tool
License: CloudLinux Commercial License
Group: System Environment/Base
Source0: %{name}-%{version}.tar.bz2
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot

BuildRequires: golang

# Disable the building of the debug package(s).
%define debug_package %{nil}

%description
This package provides Node Exporter tool


%prep
%setup -q


%build
make


%install
%{__rm} -rf $RPM_BUILD_ROOT

install -D -m 755 node_exporter $RPM_BUILD_ROOT%{_clshare_plus}/node_exporter

exit 0


%files
%{_clshare_plus}/node_exporter


%changelog

* Mon Jun 03 2020 Stepan Oksanichenko <soksanichenko@cloudlinux.com> 1.0.1-1
- CMT-18: [End Server tools] Build node exporter from sources in cloudlinux
