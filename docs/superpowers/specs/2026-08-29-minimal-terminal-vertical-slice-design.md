# Minimal Terminal-First Vertical Slice Design

## Purpose

Build the first usable LearnLab slice on a Debian 13 controller with Python 3.13. The slice proves that a user can test a named Proxmox provider, choose and start a course lesson, receive a disposable NixOS environment, retain local learning progress, and safely reset or destroy state.

The design preserves the generic hierarchy:

```text
Platform > Collection > Course > Lesson > Steps
```

Proxmox has two distinct roles:

- an infrastructure provider that creates disposable lesson environments; and
- a teachable `proxmox/proxmox-admin` collection and course that explains how to configure that provider safely.

## Scope

The first slice includes:

- a Python 3.13 `learnlab` CLI;
- named, per-user provider profiles;
- a Proxmox provider health check;
- ordered YAML curriculum discovery;
- interactive lesson selection with first-incomplete defaults;
- local SQLite progress and lifecycle state;
- clone, start, guest readiness, address discovery, stop, and delete primitives;
- per-environment SSH `known_hosts` isolation;
- scoped and global state reset behavior;
- unit, provider-contract, CLI, and opt-in live acceptance tests; and
- a minimal `proxmox/proxmox-admin` curriculum fixture sufficient to exercise the hierarchy.

The first slice does not include a web interface, remote accounts, synchronization, multi-machine lessons, automatic lesson validation, hints, template creation, provider setup mutations, or a general scheduler.

## User-Facing Commands

### Provider test

```text
learnlab provider test <profile>
```

The command loads a named provider profile and performs read-only validation. For Proxmox it verifies:

- the API is reachable and authentication succeeds;
- cluster and node discovery work;
- the configured template VM exists;
- its VMID, name, node, and template flag match the profile;
- its primary disk uses the configured storage; and
- its NIC uses the configured network.

The test explains that mutation-only permissions, including `SDN.Use` on the configured network path, cannot be proven by a read-only health check. It never creates a VM.

### Start a course

```text
learnlab start <collection>/<course> [--provider <profile>]
```

LearnLab loads the ordered lessons, local progress, and active environment state. It displays the first incomplete lesson as the default and offers a numbered list so the user may start or revisit another lesson. Steps are internal to the lesson and are presented sequentially after environment creation.

If `--provider` is omitted, the configured `default_provider` is used. A course may state required provider capabilities, but it never contains deployment-specific VMIDs, nodes, storage names, networks, API URLs, or credentials.

Only one active environment per local user and course is permitted in this slice. If one already exists, `start` reports it instead of creating another VM.

### Reset progress

```text
learnlab reset <collection>
learnlab reset <collection>/<course>
```

Reset displays the exact scope, requires confirmation, and removes progress plus completed and incomplete attempt history within that scope. It refuses to proceed while the matching scope contains an active or partially created environment. `--yes` is available for deliberate non-interactive use.

### Destroy all local environments and state

```text
learnlab destroy
```

Destroy is global for the current operating-system user. It:

1. lists every recorded environment and the Proxmox VM it will affect;
2. requires explicit confirmation before changing infrastructure;
3. asks whether completed lesson progress should be preserved;
4. stops running VMs, waits for each stop UPID, and deletes each VM;
5. waits for every delete UPID and verifies success;
6. removes per-environment SSH files and transient lifecycle state; and
7. either preserves completion records or removes all local LearnLab state, as selected.

`--yes` skips only the infrastructure confirmation. Non-interactive use must additionally specify exactly one of `--preserve-progress` or `--erase-progress`; LearnLab never guesses this choice.

An environment record is removed only after its VM is confirmed deleted or confirmed already absent. Failures leave the record available for diagnosis and retry.

## Configuration and Secrets

Non-secret configuration follows XDG conventions and defaults to:

```text
~/.config/learnlab/config.toml
```

Example:

```toml
default_provider = "home-proxmox"

[providers.home-proxmox]
type = "proxmox"
api_url = "https://pve.example:8006"
token_id = "learnlab@pve!provider"
token_secret_env = "LEARNLAB_HOME_PROXMOX_TOKEN_SECRET"
template_vmid = 9001
template_name = "nixos-26.05-base-v2"
node = "pve02"
storage = "local-lvm"
network = "vmbr0"
tls_verify = true
```

The configuration stores only the name of the environment variable containing the token secret. The secret value is never written to configuration, curriculum, source, logs, SQLite, exceptions, or test snapshots. Authorization headers and secret values are redacted from diagnostic output.

TLS verification defaults to enabled. A profile may explicitly disable it for a private lab, and the CLI emits a visible warning when it does.

## Curriculum Model

Curriculum is human-authored YAML in a version-controlled directory tree:

```text
collections/
└── proxmox/
    ├── collection.yaml
    └── courses/
        └── proxmox-admin/
            ├── course.yaml
            └── lessons/
                └── 00-api-access/
                    └── lesson.yaml
```

Each object has a stable string identifier and title. A course contains an explicit ordered list of lesson IDs; a lesson contains an explicit ordered list of steps. Explicit ordering prevents filesystem behavior from changing the learning path. Loader validation rejects duplicate IDs, missing referenced lessons, malformed course paths, and steps without unique IDs.

Curriculum may declare abstract requirements such as `proxmox.api` or `proxmox.vm.clone`. It must not name a user's provider profile or cluster resources.

## Local State

Mutable state follows XDG conventions and defaults to:

```text
~/.local/state/learnlab/learnlab.db
~/.local/state/learnlab/environments/<environment-id>/known_hosts
```

SQLite is the source of truth for:

- course and lesson progress (`not_started`, `in_progress`, `completed`);
- attempts and selected lesson;
- active and partial environment identity;
- provider profile name, provider type, VMID, node, IP address, and lifecycle phase; and
- creation and update timestamps.

The lifecycle phases are `allocating`, `cloning`, `stopped`, `starting`, `running`, `stopping`, `deleting`, and `failed`. State transitions use transactions. Remote operations cannot be atomic with SQLite, so each successful external boundary is immediately persisted. This makes interrupted work visible and cleanup retryable.

No API secret or authorization header is stored. Completed lesson progress is independent of environment records so global destroy can preserve it.

## Architecture

```text
CLI
 ├── configuration loader
 ├── curriculum catalog
 ├── progress/state store
 ├── lifecycle service
 ├── provider registry
 │    └── Proxmox provider
 └── SSH environment isolation
```

The CLI parses intent, prompts the user, and renders results. It contains no Proxmox HTTP implementation.

The curriculum catalog validates and returns collections, courses, lessons, and ordered steps without reading mutable progress.

The state store owns SQLite schema creation, transactions, progress queries, attempt records, and lifecycle transitions.

The lifecycle service coordinates state and provider calls. It is responsible for preventing duplicate active course environments and for retaining partial state after failures.

The provider registry resolves a named profile to a provider implementation. The initial provider protocol exposes health checking, VMID allocation, clone, start, status, guest readiness/address discovery, stop, existence checking, and delete.

The SSH environment component creates one `known_hosts` file per environment. It does not alter the user's normal `~/.ssh/known_hosts`. The first slice prints an SSH command using the configured identity file and isolated host-key file; it does not embed an interactive SSH client.

## Proxmox Contract

The implementation models the proven Proxmox API behavior explicitly:

| Operation | Method and path |
|---|---|
| Read VM config | `GET /nodes/{node}/qemu/{vmid}/config` |
| Allocate VMID | `GET /cluster/nextid` |
| Clone | `POST /nodes/{node}/qemu/{template_vmid}/clone` |
| Start | `POST /nodes/{node}/qemu/{vmid}/status/start` |
| Stop | `POST /nodes/{node}/qemu/{vmid}/status/stop` |
| Agent ping | `POST /nodes/{node}/qemu/{vmid}/agent/ping` |
| Guest interfaces | `GET /nodes/{node}/qemu/{vmid}/agent/network-get-interfaces` |
| Delete | `DELETE /nodes/{node}/qemu/{vmid}` |

Clone, start, stop, and delete return asynchronous UPIDs. A returned UPID means accepted, not successful. `wait_for_task` URL-encodes the UPID and polls until `status == "stopped"`; it succeeds only when `exitstatus == "OK"`. Timeouts and non-OK exits are distinct errors.

Guest readiness first retries agent ping, then reads interfaces until a non-loopback IPv4 address appears. Both phases have bounded timeouts. The IP selector ignores loopback and non-IPv4 addresses.

The provider uses the configured node for the local-storage template. After cloning it discovers the VM's actual node from cluster resources before subsequent lifecycle calls, rather than assuming placement never changes.

The bootstrap profile used during Checkpoint 05 had VMID `9001`, template name `nixos-26.05-base-v2`, node `pve02`, storage `local-lvm`, token identity `learnlab@pve!provider`, network `vmbr0`, and required scoped `SDN.Use` at `/sdn/zones/localnetwork/vmbr0`. These are documented examples and acceptance-test prerequisites, not source-code defaults.

## Start Flow

1. Parse and validate `<collection>/<course>`.
2. Load the requested course and ordered lessons.
3. Reject a duplicate active environment for that course.
4. Read progress and prompt for a lesson, defaulting to the first incomplete lesson or the first lesson when all are complete.
5. Resolve and validate the named/default provider profile and secret environment variable.
6. Create an attempt and an `allocating` environment record.
7. Allocate a VMID and persist it.
8. Clone the configured template and persist `cloning` plus the returned UPID for diagnostics.
9. Poll the task; on success persist `stopped` and the discovered actual node.
10. Start the VM, persist `starting`, and poll the task.
11. Persist `running`, wait for the guest agent and IPv4 address, then persist the address.
12. Create the isolated `known_hosts` file.
13. Mark the lesson `in_progress`, print the SSH command, and present its ordered steps.

Any exception after the environment record is created marks it `failed`, records a redacted error summary, and directs the user to `learnlab destroy`. LearnLab does not silently destroy diagnostic evidence.

## Error Handling

The CLI distinguishes configuration errors, missing secrets, authentication/authorization failures, curriculum validation errors, unexpected template identity, UPID failure, UPID timeout, guest readiness timeout, missing IPv4, state conflicts, and partial teardown.

Messages identify the failing operation and safe next action. HTTP response bodies are bounded before display and sanitized. Secrets are never included. A destroy run continues across independent environments so one failure does not prevent cleanup attempts for the others, then exits nonzero with a summary of what remains.

## Testing Strategy

All production behavior is developed test-first: write one failing behavioral test, verify the expected failure, implement the minimum code, and rerun the focused plus full suite.

Test layers are:

- unit tests for TOML loading, named profiles, secret lookup, curriculum validation and ordering, progress transitions, reset scope, destroy confirmation policy, IP selection, UPID interpretation, and secret redaction;
- state-store tests against a temporary SQLite database;
- provider contract tests against an in-process fake HTTP server that asserts exact methods, paths, form fields, authorization shape, URL-encoded UPIDs, polling behavior, and timeout/failure handling;
- CLI tests using temporary `XDG_CONFIG_HOME` and `XDG_STATE_HOME` directories, scripted prompt input, and a fake provider;
- an opt-in live Proxmox acceptance test, disabled by default, that tests allocate, clone, poll, start, guest discovery, stop, delete, and absence verification with a named profile.

Normal tests must not require network access or a real token. Live tests require an explicit marker and environment opt-in so they cannot mutate infrastructure accidentally.

## Security and Safety Invariants

- No token secret is committed or stored by LearnLab.
- Every SSH environment uses its own `known_hosts` file.
- Destructive commands display their targets and require confirmation.
- Progress preservation or erasure is always an explicit destroy choice.
- Reset cannot orphan an active environment.
- Local state is cleared only after confirmed remote cleanup.
- TLS certificate verification is enabled unless a user profile explicitly disables it.
- Live infrastructure tests are opt-in and use the same confirmed asynchronous task semantics as production.

## Success Criteria

The slice is complete when, from Debian 13 with Python 3.13, a user can:

1. configure a named Proxmox profile without storing its secret;
2. pass `learnlab provider test <profile>` against the Checkpoint 05 environment;
3. run `learnlab start proxmox/proxmox-admin`, choose a lesson, and receive a reachable NixOS VM plus isolated SSH command;
4. observe persistent local lesson progress across CLI invocations;
5. reset progress at collection or course scope with confirmation; and
6. run the confirmed global destroy flow, choose whether to preserve completed lessons, and leave no recorded disposable VM behind.
