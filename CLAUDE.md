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

## AI Workspace Required

Both the local-test and Build System workflows below assume you are inside an [AI Workspace](https://gitlab.corp.cloudlinux.com/clos/ci-tools/cl-aiworkspaces) VM at `/root/ai-workspace/`. They depend on:

- the workspace's CloudLinux OS toolchain and any project-specific runtime (Python venv, Node, Docker, …) — needed by the local-build and unit-test targets;
- the workspace's `mcp-cli-wrapper.sh` and provisioned Build System / Jenkins tokens — needed by the BS payload helper.

Outside an AI Workspace these commands will not work as documented. Spin up a workspace via `cl-aiworkspaces` first.

## Local Tests

Run from the repo root (`/root/ai-workspace/node_exporter/`):

| Command | What it does |
| --- | --- |
| `make build` | Build the `node_exporter` binary |
| `make test` | Run the upstream Go unit-test suite |
| `make test-e2e` | Run the e2e harness (downloads collector fixtures on first run) |
| `make checkmetrics && make checkrules` | Validate metric and rule schemas |

## Build System

This repo ships as an RPM/DEB package: `node_exporter`. **Use the `/build-create` skill to submit builds** — it runs `build-plan.py` and submits the payload via the Build System CLI. The tables below are the project-specific overrides on top of that generic flow.

### Parameters

Most fields come from `build-plan.py`; the table records what should end up in the final payload for a `node_exporter`-only build.

| Field | Value |
| --- | --- |
| BS project name | `node_exporter` |
| `build_type_id` | `5ac2787bdf7e526d4a5f0259` (CloudLinux OS packages) |
| `build_platforms` | `CL7`, `CL8`, `CL9`, `CL10`, `ubuntu22_04_ext_cpanel` |
| `build_flavors` | `alt-php-els` (id `68b1ad89aa0264b2618434c8`) |
| `target_channel` | `beta` |
| `build_ref.name` | **Branch (or tag) to build.** `build-plan.py` reads this from the current `git` checkout in the workspace — confirm you are on the intended branch (your feature branch, not `master`) before generating the plan. |
| `build_ref.type` | `git_branch` or `git_tag`. |
| `testing.qa_ref` (per project) and top-level `qa_ref` | **Branch checked out in the QA repo for Jenkins jobs.** `build-plan.py` defaults both to `"master"` regardless of `build_ref.name` — override to your feature branch if the QA side has matching changes. |

### Jenkins jobs (node_exporter-relevant)

`build-plan.py` emits the workspace-wide plan covering every project in the workspace. For a `node_exporter`-only build, filter `projects[]` down to `node_exporter` and keep **only** these jobs in `jenkins_jobs[]`:

| Job name | Build System `_id` |
| --- | --- |
| `CMT-end-server-tools` | `635b962c2afd3e1feec603bd` |
| `clpro-ubuntu-tests` | `677e40a2f1b69faa0d69baf6` |
