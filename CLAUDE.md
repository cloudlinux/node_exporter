# node_exporter (CloudLinux fork)

This repository is CloudLinux's fork of the upstream
[prometheus/node_exporter](https://github.com/prometheus/node_exporter). It is
packaged as `cl-node-exporter` (RPM) and `cl-node-exporter` (deb) and is
consumed internally by the `cl_plus` telemetry stack. Upstream `master` is
merged in periodically; all CloudLinux-specific changes live on top of the
upstream history.

## What the fork adds

The fork is deliberately small. Out of the box upstream, plus:

1. A unix-socket transport for `/metrics` (`--web.socket-path`,
   `--web.socket-permissions`).
2. CloudLinux packaging recipes (`node_exporter.spec`, `debian/`).
3. A versioned tests subpackage at `/opt/node_exporter_tests/` used by the
   CloudLinux QA pipeline.
4. A `/usr/share/cloudlinux/cl-node-exporter` version file, read by Sentry
   for package-version tagging.
5. A Makefile change that runs `test-e2e` twice (TCP + unix-socket) so the
   fork-local feature is exercised on every build.

Everything else in this repo — collectors, metric semantics, command-line
flags, build targets — is upstream and should be understood by reading
upstream documentation, not by treating this repo as authoritative.

## Design Specifications

This project maintains design specs for the features where business rules,
invariants, and CloudLinux-specific decisions are not obvious from source
code. Check the index below before starting work — read any spec that
relates to your task. If your changes affect behavior described in a spec,
update the spec in the same commit.

- [Unix Socket Listener](docs/design/unix-socket-listener.md) — `--web.socket-path`, `--web.socket-permissions`, unix domain socket, cl_plus scraping, socket cleanup, SIGTERM shutdown, e2e `-s` flag, `node_exporter.go` main
- [CloudLinux Packaging](docs/design/cloudlinux-packaging.md) — `cl-node-exporter` RPM, deb, `node_exporter.spec`, `debian/rules`, `/usr/share/cloudlinux/cl_plus/`, version file, Sentry tagging, tests subpackage, pinned Go toolchain, amd64-only

## Working on this fork

- **Before changing CloudLinux-specific code** (unix socket, RPM/deb
  recipes, `/usr/share/cloudlinux/*` layout): read the relevant design
  spec first, and update it in the same commit as your code change.
- **Before changing upstream-owned files** (anything under `collector/`,
  `node_exporter.go` outside the unix-socket block, Makefile targets not
  listed above): prefer forwarding the change upstream. Fork-local diffs
  make the next upstream sync harder.
- **Upstream syncs:** history from upstream is merged periodically (see
  commits tagged `Sync ... with upstream`). When resolving conflicts,
  preserve every CloudLinux-specific invariant listed in the design
  specs; if upstream has reimplemented something equivalent (e.g. unix
  socket support), prefer deleting the fork-local copy and documenting
  the change.
