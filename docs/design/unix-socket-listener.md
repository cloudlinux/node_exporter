# Unix Socket Listener — Design Specification

## Overview

This CloudLinux fork adds the ability to expose the `/metrics` endpoint over a
filesystem unix domain socket instead of a TCP port. The feature exists so that
other CloudLinux end-server tooling (the primary consumer being `cl_plus`) can
scrape `node_exporter` locally without opening a network port or relying on
HTTP authentication/TLS. Access control is delegated to filesystem permissions
on the socket file.

This feature is CloudLinux-specific — it does not exist in upstream
`prometheus/node_exporter`, and exporter-toolkit (checked up to v0.21.0) has
no unix socket listener either.

## Flags

| Flag | Default | Behavior |
|------|---------|----------|
| `--web.socket-path` | `""` (empty — disabled) | Filesystem path of the unix socket to listen on. When non-empty, disables the upstream TCP/TLS listener entirely. |
| `--web.socket-permissions` | `0640` | `chmod` bits applied to the socket file after it is created. Accepts an integer (octal literal recognised by Go's `Int32` parser). |

Flags are parsed by `kingpin` and defined in `main()` in `node_exporter.go`.
Both flags ship in the fork's main package and are always visible in
`--help`, regardless of OS. The upstream web flags are registered by
exporter-toolkit's `bootstrap.New`: `--web.listen-address`,
`--web.config.file` and `--web.systemd-socket` are still present but are
ignored when `--web.socket-path` is set (see Invariants below);
`--web.telemetry-path`, `--web.disable-exporter-metrics` and
`--web.max-requests` apply to both transports.

## Mechanism

Upstream (since v1.13.0) starts the exporter through exporter-toolkit's
`bootstrap.Runner`: `runner.Run()` parses the flags, calls the runner's
`MetricsHandlerFactory`, builds the HTTP mux (metrics path, landing page,
routes the factory registered, e.g. `/debug/pprof/`) and then opens the
listeners with `web.ListenAndServe` (TCP, vsock or systemd sockets). The
toolkit offers no hook to replace the listener, so the fork hooks in at the
factory: after `bootstrap.New`, `main()` wraps `runner.MetricsHandlerFactory`
with `unixSocketFactory` (`node_exporter.go`). Bootstrap calls the factory
after parsing flags and before opening any listener.

When `--web.socket-path` is empty (default), the wrapper returns the upstream
handler unchanged and bootstrap serves TCP (+ optional TLS) exactly as
upstream does. When it is non-empty, the wrapper builds the upstream handler
and calls `serveUnixSocket`, which never returns to bootstrap on success:

1. Registers on `http.DefaultServeMux` what bootstrap serves over TCP: the
   metrics path wrapped in `Bootstrap.MaxRequestsHandler`
   (`--web.max-requests`), the landing page built from `runner.LandingConfig`
   unless the metrics path is `/`, and `net/http/pprof`, which registers
   itself on `DefaultServeMux`.
2. Logs the `Starting node_exporter` and `Build context` lines that
   `runner.Run()` logs before listening.
3. Calls `os.Remove` on the socket path before binding. Any pre-existing file
   (stale socket from a previous run, regular file, symlink) is removed
   unconditionally.
4. Binds a `net.Listen("unix", path)` listener.
5. `chmod`s the newly created socket to `--web.socket-permissions`. If the
   chmod fails, the error is returned: the listener is closed, which also
   removes the socket file, and `main()` exits 1 with the error on stderr.
6. Serves plain HTTP over the unix listener in a goroutine, with the same
   `ReadHeaderTimeout` (one minute) as bootstrap's TCP server.
   `--web.config.file` (TLS, basic auth) is not applied to the socket.
7. Installs a `SIGINT` / `SIGTERM` handler. On signal the server is closed,
   the socket file is `os.Remove`d and the process exits 0. If serving fails
   instead, the error is returned, the deferred listener close removes the
   socket file and `main()` exits 1.

Bind errors are returned the same way (exit 1, error on stderr). Because the
wrapper does not return to bootstrap in socket mode, `web.ListenAndServe` is
never called and no TCP listener exists in that process.

`SIGHUP` is not handled in either mode: Go's default action terminates the
process and leaves the socket file behind (unchanged from earlier releases).
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
  fails if the socket file is still present after shutdown.
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
| Default permissions are applied | `end-to-end-test.sh -s` | E2E | Without `--web.socket-permissions` (as `cl_plus` runs it) the socket file's `ls -ld` mode string starts with `srw-r-----`. |
| No TCP listener in socket mode | `end-to-end-test.sh -s` | E2E | The exporter also gets `--web.listen-address=127.0.0.1:<port>`; `curl` to that address must fail with exit code 7 (connection refused) while the socket serves metrics. This shows bootstrap never opens its listeners; it does not look for TCP listeners on other addresses. The check uses only `ls` and `curl`, which the script already needs, so it runs unchanged on Linux and on the BSD, Solaris and macOS jobs of the upstream workflows. |
| Non-default permissions, ignored TCP flags, SIGTERM exit | `TestUnixSocket` in `node_exporter_test.go` | Go (runs the binary) | `--web.socket-permissions 0600` gives a `0600` socket; the `--web.listen-address` passed alongside is not served; SIGTERM exits 0 and removes the socket. Like the other binary tests there, it is skipped unless the binary is at `$GOPATH/bin/node_exporter`, so it does not run in package builds. |

### Known gaps

- **Concurrent-start / stale-socket scenarios are barely tested.** The e2e
  suite pre-creates the socket path as a regular file, so removal of a
  stale file at startup is exercised, but a stale socket left by a crashed
  process and two exporters racing on the same path are not.
- **Chmod-failure path is not tested.** Exit behaviour when `chmod` fails
  (e.g., socket path on a filesystem that rejects mode changes) is not
  exercised.
- **Signal-handling coverage is shallow.** Only the graceful
  `SIGINT`/`SIGTERM` path is exercised; `SIGKILL` or panic paths (which
  leak the socket file by design) are not asserted anywhere.
- **Ignoring TCP flags in socket mode is silent.** A user passing both
  `--web.listen-address` and `--web.socket-path` gets socket-only behaviour
  (asserted by `TestUnixSocket` and `end-to-end-test.sh -s`); this is not
  documented in `--help` or reported at flag-parse time.
