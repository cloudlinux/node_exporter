Autoreq: 0
%define cl_dir /usr/share/cloudlinux/
%define _clshare_plus %{cl_dir}cl_plus
%define pkg_version_file %{cl_dir}%{name}

Name: cl-node-exporter
Version: 1.2.0
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
curl https://dl.google.com/go/go1.24.0.linux-amd64.tar.gz --output %{_tmppath}/go.tar.gz
%else
curl https://dl.google.com/go/go1.24.0.linux-386.tar.gz --output %{_tmppath}/go.tar.gz
%endif
tar xzf %{_tmppath}/go.tar.gz -C %{_tmppath}
export PATH=$PATH:%{_tmppath}/go/bin
export GOROOT=%{_tmppath}/go
export GOPATH=%{_tmppath}
make build
make tools
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
mkdir -p $RPM_BUILD_ROOT/opt/node_exporter_tests/tools
install -D -m 755 tools/tools $RPM_BUILD_ROOT/opt/node_exporter_tests/tools/tools

# remove broken symlinks
find $RPM_BUILD_ROOT/opt/node_exporter_tests/collector/fixtures -xtype l -delete

# write package version to file
if [[ ! -d "$RPM_BUILD_ROOT%{cl_dir}" ]]; then
    mkdir -p $RPM_BUILD_ROOT%{cl_dir}
fi
echo "%{version}-%{release}" > $RPM_BUILD_ROOT%{pkg_version_file}

exit 0


%files
%{_clshare_plus}/node_exporter
%{pkg_version_file}

%files tests
/opt/node_exporter_tests/*


%changelog

* Mon Dec 01 2025 Ruslan Koliada <rkoliada@cloudlinux.com> 1.2.0-1
- CLPRO-2902: Sync repository with upstream

* Wed Aug 19 2020 Stepan Oksanichenko <soksanichenko@cloudlinux.com> 1.1.0-2
- CMT-221: Add package versions tags to sentry

* Fri Jun 26 2020 Stepan Oksanichenko <soksanichenko@cloudlinux.com> 1.1.0-1
- CMT-75: Added ability to use unix socket instead http connection

* Mon Jun 03 2020 Stepan Oksanichenko <soksanichenko@cloudlinux.com> 1.0.1-1
- CMT-18: [End Server tools] Build node exporter from sources in cloudlinux
