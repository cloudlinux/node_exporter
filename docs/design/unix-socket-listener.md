# Unix Socket Listener — Design Specification

## Overview

This CloudLinux fork adds the ability to expose the `/metrics` endpoint over a
filesystem unix domain socket instead of a TCP port. The feature exists so that
other CloudLinux end-server tooling (the primary consumer being `cl_plus`) can
scrape `node_exporter` locally without opening a network port or relying on
HTTP authentication/TLS. Access control is delegated to filesystem permissions
on the socket file.

This feature is CloudLinux-specific — it does not exist in upstream
`prometheus/node_exporter`.

## Flags

| Flag | Default | Behavior |
|------|---------|----------|
| `--web.socket-path` | `""` (empty — disabled) | Filesystem path of the unix socket to listen on. When non-empty, disables the upstream TCP/TLS listener entirely. |
| `--web.socket-permissions` | `0640` | `chmod` bits applied to the socket file after it is created. Accepts an integer (octal literal recognised by Go's `Int32` parser). |

Flags are parsed by `kingpin` and defined in `node_exporter.go`. Both flags
ship in the fork's main package and are always visible in `--help`, regardless
of OS. Upstream flags (`--web.listen-address`, `--web.config.file`,
`--web.systemd-socket`) are still present but are mutually exclusive with
`--web.socket-path` at runtime (see Invariants below).

## Mechanism

When `--web.socket-path` is non-empty, the exporter:

1. Calls `os.Remove` on the socket path before binding. Any pre-existing file
   (stale socket from a previous run, regular file, symlink) is removed
   unconditionally.
2. Binds a `net.Listen("unix", path)` listener.
3. `chmod`s the newly created socket to `--web.socket-permissions`. If the
   chmod fails, the socket file is removed and the process exits non-zero.
4. Serves HTTP over the unix listener in a goroutine.
5. Installs a `SIGINT` / `SIGTERM` handler. On signal the server is closed and
   the socket file is `os.Remove`d before exit (exit code 0).
6. Registers a `defer os.Remove` on the socket path as a secondary cleanup in
   case the signal handler path is bypassed.

When `--web.socket-path` is empty (default), the exporter falls through to the
upstream `web.ListenAndServe(...)` path using `toolkitFlags` (TCP + optional
TLS). The unix-socket branch and the TCP branch are mutually exclusive in the
same process.

## Invariants

- **Exclusive listener.** When `--web.socket-path` is non-empty, no TCP
  listener is opened. `--web.listen-address`, TLS config, and systemd socket
  activation are ignored for that run.
- **Socket is always removed on startup.** The exporter unconditionally
  `os.Remove`s the path before binding. Operators must not point
  `--web.socket-path` at a non-socket file they care about.
- **Socket is always removed on clean shutdown.** On `SIGINT`/`SIGTERM`, or
  on any error path after successful bind, the socket file must not be left
  behind. The e2e test `end-to-end-test.sh -s` asserts this explicitly and
  fails the build if the socket file is still present after shutdown.
- **Permissions are applied before first accept.** The chmod step happens
  synchronously before the `Serve` goroutine is started, so no client can
  connect to an over-permissive socket.
- **Permissions failure is fatal.** If chmod fails, the socket file is
  removed and the exporter exits non-zero rather than serving with
  unintended permissions.
- **Default `0640` is intentional.** It allows the exporter process (owner)
  to write and a scraping group (e.g., the `cl_plus` group) to read, while
  denying world access. Operators overriding this value take responsibility
  for access control.

## Packaging Integration

The `cl-node-exporter` RPM and deb packages install the binary at
`/usr/share/cloudlinux/cl_plus/node_exporter`. They do **not** ship a
systemd unit or a default socket path — the invoking CloudLinux service
(external to this repo) is responsible for choosing the socket path, owning
its parent directory, and setting the scraping group.

## Test Coverage

| Aspect | Test | Type | Covers |
|--------|------|------|--------|
| Metrics over unix socket match metrics over TCP | `end-to-end-test.sh -s` (invoked by `make test-e2e`) | E2E | Full `/metrics` exposition via `curl --unix-socket` must diff-equal the fixture produced via TCP. |
| Socket file is removed on clean shutdown | `end-to-end-test.sh` finish trap (socket mode) | E2E | After SIGTERM, `ls` on the socket path must fail; test exits non-zero otherwise. |
| Both transports still work after refactors | `Makefile` `test-e2e` target | E2E | Runs the e2e suite twice — once with TCP (`--web.listen-address`) and once with `--web.socket-path`. |

### Known gaps

- **Permission mode semantics are not tested.** No automated test verifies
  that `--web.socket-permissions` actually produces the requested mode on
  disk, nor that a non-default value (e.g., `0600`, `0660`) is honoured.
- **Concurrent-start / stale-socket scenarios are not tested.** The e2e
  suite does not cover the case where a previous process crashed leaving a
  socket file behind, nor the case where two exporters race on the same
  path.
- **Chmod-failure path is not tested.** Exit behaviour when `chmod` fails
  (e.g., socket path on a filesystem that rejects mode changes) is not
  exercised.
- **Signal-handling coverage is shallow.** Only the graceful
  `SIGINT`/`SIGTERM` path is exercised; `SIGKILL` or panic paths (which
  leak the socket file by design) are not asserted anywhere.
- **No assertion that TCP flags are ignored in socket mode.** A user
  passing both `--web.listen-address` and `--web.socket-path` gets
  socket-only behaviour silently; this is not documented in `--help` or
  checked at flag-parse time.
