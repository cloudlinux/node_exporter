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

## Creating a Build

This project ships as an RPM package (Build System name: `node_exporter`). Builds are submitted to the CloudLinux Build System via its CLI.

### Step 1 — Generate the build plan

```bash
cd /root/ai-workspace/node_exporter
git checkout <branch-or-tag>                # branch, tag, or detached HEAD
uv run /root/ai-workspace/cl-aiworkspaces/workspace-side/scripts/build-plan.py
```

The script reads `cl-aiworkspaces/.agents/skills/build-create/projects-catalog.yaml` to map this workspace directory to its Build System name(s) and emits a JSON plan on stdout (warnings/errors on stderr; exit 1 on fatal errors such as uncommitted changes).

The plan contains:
- `build_type_id` — build-type for the payload
- `build_platforms` — target platforms (e.g. CL7, CL8, CL9)
- `build_flavors` — flavor IDs
- `projects` — project names, build refs, testing config
- `jenkins_jobs` — Jenkins job IDs and definitions

### Step 2 — Filter the plan to this project only

The plan may include unrelated workspace projects. **Strip all entries from `projects` except `node_exporter`**, and keep only the Jenkins jobs relevant to it. One project per build — do not submit a multi-project payload.

### Step 3 — Submit the build

```bash
/root/ai-workspace/cl-aiworkspaces/workspace-side/mcps/mcp-cli-wrapper.sh build-system \
  create-build --raw '<filtered-plan-json>'
```

Minimum payload shape:

```json
{
  "build_type_id": "<from plan>",
  "build_platforms": [<from plan>],
  "build_flavors": ["<flavor_id>"],
  "target_channel": "beta",
  "projects": [
    {
      "name": "node_exporter",
      "build_ref": { "name": "<branch-or-tag>", "type": "git_branch" },
      "testing": { "qa_ref": "<branch-or-tag>" }
    }
  ],
  "jenkins_jobs": [<from plan — only jobs relevant to this project>]
}
```

`build_ref.type` options: `git_branch`, `git_tag`, or `gerrit_change` (for `refs/changes/XX/NNNNN/PS` refs — the `qa_ref` should then be `NNNNN/PS`).

The CLI returns a build ID. Build URL: `https://build.cloudlinux.com/#/build/<build_id>`.

### Step 4 — Monitor

```bash
/root/ai-workspace/cl-aiworkspaces/workspace-side/mcps/mcp-cli-wrapper.sh build-system \
  get-build --build-id <build_id>
```

### Step 5 — Debug failures

Search logs for errors:

```bash
/root/ai-workspace/cl-aiworkspaces/workspace-side/mcps/mcp-cli-wrapper.sh build-system \
  search-build-logs --build-id <build_id> --query "error"
```

Common failure patterns:

| Symptom | Likely cause | Fix |
|---|---|---|
| `FAILED` in test output | Test regression | Update the test — do not revert the code fix |
| `ModuleNotFoundError` / `ImportError` | New dependency not declared | Add to the `.spec` `Requires`/`BuildRequires` (or equivalent) |
| `SyntaxError` in build log | Source typo | Fix the source |
| `%files`/`%install` mismatch | Spec file vs installed layout drift | Update the spec stanzas |
| Dependency-resolution errors | `Requires` constraint wrong | Check spec file version constraints |

After fixing, push to the same branch and re-run steps 1–3.
