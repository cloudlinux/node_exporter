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
| `/opt/node_exporter_tests/end-to-end-test.sh` | E2E harness script. |
| `/opt/node_exporter_tests/collector/` | Fixture data (procfs/sysfs/udev snapshots). Broken symlinks under `fixtures/` are stripped during `%install` because dh on Ubuntu rejects them. |
| `/opt/node_exporter_tests/tools/tools` | Build-tag matcher helper used by the e2e script. |

This subpackage exists so the QA pipeline can run the upstream e2e suite on
the exact binary that ships, including the CloudLinux unix-socket mode (see
`unix-socket-listener.md`).

## Build Mechanism

Both packages download and use a pinned upstream Go toolchain at build time
rather than relying on the distro's `golang` package:

- **Pinned version: `go1.24.0`.** Hard-coded in both `node_exporter.spec`
  (`%build` section) and `debian/rules` (`override_dh_auto_build`).
- **Source:** `https://dl.google.com/go/go1.24.0.linux-<arch>.tar.gz`.
- **Location:** extracted to `%{_tmppath}/go` (RPM) or `/tmp/go` (deb).
- The pinned toolchain is prepended to `PATH` for the duration of the build.

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

- After install, `find $buildroot/opt/node_exporter_tests/collector/fixtures
  -xtype l -delete` removes broken symlinks produced by the procfs fixture
  ttar archive. Without this, `dh_*` fails the build on Ubuntu.
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
- **Both architectures are amd64-only today.** Both `node_exporter.spec`
  (via the `%ifarch` x86_64/amd64/ia32e branches being the only curl'd Go
  archives) and `debian/control` (`Architecture: amd64`) restrict the
  package to x86_64. Adding another arch requires touching both recipes.

## Test Coverage

| Aspect | Test | Type | Covers |
|--------|------|------|--------|
| Binary builds and e2e passes on RPM build workers | `%build` section of `node_exporter.spec` runs `make build`, `make test`, `make test-32bit` | RPM build-time | Compilation + unit tests + 32-bit cross-compile + e2e socket/TCP tests (`make test-e2e`) on RPM workers. Failure aborts the build. |
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
- **Tests subpackage is not smoke-tested after install.** No CI job
  installs `cl-node-exporter-tests` on a fresh VM and runs
  `/opt/node_exporter_tests/end-to-end-test.sh` against the shipped
  binary.
- **No coverage for non-amd64 targets.** Non-x86_64 arches are not built
  and therefore not exercised at all for the RPM or deb paths, even
  though upstream supports them.
- **Deb does not run e2e.** `override_dh_auto_build` intentionally skips
  `make test-e2e`, so the unix-socket listener is not exercised on Ubuntu
  build workers.
