Autoreq: 0
%define _clshare_plus /usr/share/cloudlinux/cl_plus

Name: cl-node-exporter
Version: 1.0.1
Release: 1%{dist}.cloudlinux
Summary: CL Node Exporter tool
License: Apache License, Version 2.0
Group: System Environment/Base
Source0: %{name}-%{version}.tar.bz2
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot


# Disable the building of the debug package(s).
%define debug_package %{nil}


%package tests
Summary: Tests for CL Node Exporter version %{version}
AutoReq: 0
Group: Applications/System
License: Apache License, Version 2.0


%description
This package provides Node Exporter tool

%description tests
This package provides end-to-end tests for Node Exporter tool


%prep
%setup -q


%build
# download new version of Go compiler
%ifarch x86_64 amd64 ia32e
curl https://dl.google.com/go/go1.14.4.linux-amd64.tar.gz --output %{_tmppath}/go.tar.gz
%else
curl https://dl.google.com/go/go1.14.4.linux-386.tar.gz --output %{_tmppath}/go.tar.gz
%endif
tar xzf %{_tmppath}/go.tar.gz -C %{_tmppath}
export PATH=$PATH:%{_tmppath}/go/bin
export GOROOT=%{_tmppath}/go
export GOPATH=%{_tmppath}
make build
make test
# run cross-testing
%ifarch x86_64 amd64 ia32e
make test-32bit
%endif

# build tests
rm -rf collector/fixtures/sys
./ttar -C collector/fixtures -x -f collector/fixtures/sys.ttar


%install
rm -rf $RPM_BUILD_ROOT

install -D -m 755 node_exporter $RPM_BUILD_ROOT%{_clshare_plus}/node_exporter

#install tests
mkdir -p $RPM_BUILD_ROOT/opt/node_exporter_tests/collector
cp -r collector/fixtures $RPM_BUILD_ROOT/opt/node_exporter_tests/collector/
install -D -m 755 end-to-end-test.sh $RPM_BUILD_ROOT/opt/node_exporter_tests/end-to-end-test.sh
install -D -m 755 node_exporter $RPM_BUILD_ROOT/opt/node_exporter_tests/node_exporter

exit 0


%files
%{_clshare_plus}/node_exporter

%files tests
/opt/node_exporter_tests/*


%changelog

* Mon Jun 03 2020 Stepan Oksanichenko <soksanichenko@cloudlinux.com> 1.0.1-1
- CMT-18: [End Server tools] Build node exporter from sources in cloudlinux
