# CloudLinux Packaging — Design Specification

## Overview

This fork is shipped as the `cl-node-exporter` RPM (for CloudLinux OS 7/8/9,
AlmaLinux) and `cl-node-exporter` `.deb` (for Ubuntu 20.04 / 22.04 servers
running CloudLinux components). Packages are built from this repository's
`node_exporter.spec` and `debian/` tree. The binary is installed into the
CloudLinux-private tree (`/usr/share/cloudlinux/cl_plus/`) rather than onto
`$PATH`, because it is an internal component of the `cl_plus` telemetry
stack, not a general-purpose system service. This spec covers only
packaging-level invariants — runtime flags are covered in other specs.

## Package Layout

### Binary package `cl-node-exporter`

| Path | Source | Purpose |
|------|--------|---------|
| `/usr/share/cloudlinux/cl_plus/node_exporter` | `node_exporter` binary, built from source during packaging | The exporter binary. Executed by the external `cl_plus` service; not intended to be invoked by operators directly. |
| `/usr/share/cloudlinux/cl-node-exporter` | Generated during `%install` / `override_dh_auto_install` | Plain-text file containing `<version>-<release>`. Consumed by Sentry for package-version tagging of crash reports. |

The package deliberately omits: a systemd unit, a default config file, a
`/usr/bin/` symlink, any `sysusers.d` entry, and any firewall or SELinux
policy. All lifecycle and configuration concerns are owned by the consumer
package (`cl_plus`).

### Tests subpackage `cl-node-exporter-tests`

| Path | Purpose |
|------|---------|
| `/opt/node_exporter_tests/node_exporter` | Second copy of the built binary, used by the e2e harness. |
| `/opt/node_exporter_tests/end-to-end-test.sh` | E2E harness script. Needs `curl` and `diff` (diffutils), and for `-s` also `stat` and `ss` (iproute), on the test host; the subpackage declares no dependencies (`AutoReq: 0`). |
| `/opt/node_exporter_tests/collector/` | Fixture data (procfs/sysfs/udev snapshots). Both recipes strip broken symlinks under `fixtures/` during install, so the package ships none (see Invariants). The five broken `sys/block/dm-*/slaves/*` links are replaced by empty regular files of the same name instead: the diskstats collector only lists the entry names there (procfs `SysBlockDeviceUnderlyingDevices`, `Readdirnames`) for `node_disk_device_mapper_backing_device_info` (upstream v1.13.0+), and without them the e2e output misses five series in both modes. |
| `/opt/node_exporter_tests/tools/tools` | Build-tag matcher helper used by the e2e script. |

This subpackage exists so the QA pipeline can run the upstream e2e suite on
the exact binary that ships, including the CloudLinux unix-socket mode (see
`unix-socket-listener.md`).

## Build Mechanism

Both packages download and use a pinned upstream Go toolchain at build time
rather than relying on the distro's `golang` package:

- **Pinned version: `go1.27.4`.** Hard-coded in both `node_exporter.spec`
  (`%build` section) and `debian/rules` (`override_dh_auto_build`). It must
  be at least the `go` directive in `go.mod` (`1.26.0` at upstream v1.13.1):
  with an older toolchain the go command's default `GOTOOLCHAIN=auto`
  silently downloads the required toolchain from `proxy.golang.org` (the
  1.2.1 package pinned `go1.24.0` but its binary reports `go1.25.0`). The
  pin follows the Go line upstream builds releases with (`.promu.yml`,
  `setup-go` in `.github/workflows/ci.yml`), at its latest patch release.
- **Source:** `https://dl.google.com/go/go1.27.4.linux-<arch>.tar.gz`
  (`amd64`; the spec's non-x86_64 branch fetches `386`). The archive is not
  checksum-verified by the recipes; the published SHA-256 values are listed
  at `https://go.dev/dl/?mode=json`.
- **Location:** extracted to `%{_tmppath}/go` (RPM) or `/tmp/go` (deb).
- The pinned toolchain is appended to `PATH` in the spec (a `go` already on
  the builder's `PATH` would win) and prepended in `debian/rules`.
- Go modules are not vendored: `make build` / `make test` download them
  from the Go module proxy, and `make build` downloads `promu` from GitHub,
  so build workers need internet access.

RPM spec also runs 32-bit cross-testing (`make test-32bit`) on x86_64/amd64
builds. The deb rules do not.

### RPM-only conventions (`node_exporter.spec`)

- `Autoreq: 0` and `%define debug_package %{nil}` — auto-dependency scanning
  and debuginfo generation are disabled because the binary is a statically
  linked Go artifact.
- Version file path is derived from macros: `%{cl_dir}%{name}` resolves to
  `/usr/share/cloudlinux/cl-node-exporter`. The file's content is
  `%{version}-%{release}` as a single line.

### Debian-only conventions (`debian/rules`)

- `dh_movefiles` moves only files and symlinks, so empty fixture
  directories (e.g. `sys/block/dm-5/slaves/sd*`, listed by the dmmultipath
  collector) are created in the tests package directly with
  `find -type d -empty -exec install -d`. Without them the deb tests
  package's e2e misses the `node_dmmultipath_*` path series. QA does not
  run the e2e on Ubuntu, so only a manual run catches this.
- `override_dh_auto_clean` only removes `debian/tmp` — it does not invoke
  `make clean`, so the vendored Go toolchain in `/tmp/go` may persist
  between builds on a long-lived worker.
- Release string is hard-coded as `.ubuntu.cloudlinux` (parsed from the
  `debian/changelog` version by `dpkg-parsechangelog`).

## Invariants

- **Install path is stable.** `/usr/share/cloudlinux/cl_plus/node_exporter`
  is a contract with the consumer package. Moving the binary requires a
  coordinated change in `cl_plus`.
- **Version file is stable.** `/usr/share/cloudlinux/cl-node-exporter`
  contains exactly `<rpm-or-deb-version>-<release>` and is consumed by
  Sentry tagging. Format change requires coordinating with the reporter.
- **Go toolchain is pinned in the recipe, not the CI image.** The pinned
  version lives in `node_exporter.spec` and `debian/rules`. Bumping Go
  means editing both files in the same commit.
- **The binary package does not own any runtime config, user, or unit.**
  All CloudLinux-specific runtime wiring (socket path, user, scraping
  group, startup ordering) is owned by the consumer.
- **Tests subpackage is optional.** The binary package must function
  without `cl-node-exporter-tests` installed; the test subpackage is a
  QA-only artifact.
- **No dangling symlinks in either package.** QA's
  `rpm_tests/common/0_integrity_check.bats` ("symlinks are correct and
  exists") fails a package with a symlink to a missing target, on every
  target including Ubuntu. Fixture links that dangle after extraction are
  deleted, or, where a collector needs the entry name, replaced by an empty
  file in both recipes.
- **Both architectures are amd64-only today.** Both `node_exporter.spec`
  (via the `%ifarch` x86_64/amd64/ia32e branches being the only curl'd Go
  archives) and `debian/control` (`Architecture: amd64`) restrict the
  package to x86_64. Adding another arch requires touching both recipes.

## Test Coverage

| Aspect | Test | Type | Covers |
|--------|------|------|--------|
| Binary builds and unit tests pass on RPM build workers | `%build` section of `node_exporter.spec` runs `make build`, `make tools`, `make test`, `make test-32bit` | RPM build-time | Compilation + unit tests (with `-race` on x86_64) + 32-bit cross-compile tests on RPM workers. Failure aborts the build. `make test-e2e` is not run here; the root-package tests that need a built binary skip (it is not at `$GOPATH/bin`). |
| E2E over TCP and unix socket on the shipped binary | `rpm_tests/p_cl-node-exporter` in the QA repo runs `/opt/node_exporter_tests/end-to-end-test.sh` and `-s` | QA (installed package) | Both runs must exit 0 with no output. Ubuntu is skipped there (covered by `cl-end-server-tools` tests). |
| Packages ship no dangling symlinks | `rpm_tests/common/0_integrity_check.bats` in the QA repo ("symlinks are correct and exists") | QA (installed package) | Every symlink in `cl-node-exporter` and `cl-node-exporter-tests` must resolve; runs on all targets including Ubuntu. |
| Binary builds on Ubuntu build workers | `override_dh_auto_build` in `debian/rules` runs `make build`, `make tools`, `make test` | deb build-time | Compilation + unit tests on Ubuntu. (No `test-e2e` is wired in deb.) |
| Fixture ttar archive is extractable | `make test-e2e` depends on `collector/fixtures/sys/.unpacked` and `collector/fixtures/udev/.unpacked` | Build | If the ttar archives are corrupt or missing, the build fails at extraction time. |

### Known gaps

- **No packaging-smoke test.** Nothing verifies post-install that
  `/usr/share/cloudlinux/cl_plus/node_exporter --version` returns the
  expected version string, or that the version file content matches the
  package version. A trivial `%posttrans` or `debian/postinst` smoke check
  would close this.
- **Version-file format is not asserted.** If a future change to the spec
  accidentally drops the newline, quotes the string, or appends the
  architecture, Sentry tagging will silently degrade.
- **Tests subpackage runs on RPM systems only.** QA's
  `rpm_tests/p_cl-node-exporter` installs `cl-node-exporter-tests` and runs
  the e2e harness against the shipped binary on CloudLinux, but skips
  Ubuntu.
- **No coverage for non-amd64 targets.** Non-x86_64 arches are not built
  and therefore not exercised at all for the RPM or deb paths, even
  though upstream supports them.
- **Deb does not run e2e.** `override_dh_auto_build` intentionally skips
  `make test-e2e`, so the unix-socket listener is not exercised on Ubuntu
  build workers.
