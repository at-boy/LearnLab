# LearnLab

LearnLab is a terminal-first learning environment that creates disposable
Proxmox VMs for ordered lessons and keeps progress locally.

## Install on Debian 13

Install Python 3.13 and its virtual-environment support, then install LearnLab
in an isolated environment from this checkout:

```bash
sudo apt install python3.13 python3.13-venv
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

The configuration file follows XDG conventions. Its usual location on Debian
is `~/.config/learnlab/config.toml` (or
`$XDG_CONFIG_HOME/learnlab/config.toml` when `XDG_CONFIG_HOME` is set). LearnLab
stores its local SQLite state and isolated SSH host-key files under
`~/.local/state/learnlab` by default.

Create the configuration directory before writing the file:

```bash
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/learnlab"
```

## Configure a named Proxmox profile

Need to build the template first? Follow the draft
[NixOS Template Guide](docs/NixOS-Template-Guide.md), or start its seven-lesson
bootstrap course on your controller without a provider profile:

```bash
learnlab start proxmox/nixos-template --include-drafts
```

LearnLab records local, self-attested progress; you operate Proxmox and the guest
explicitly. The guide covers ISO installation, trusted access, identity sealing,
two-clone acceptance, a new named profile and cleanup of only those test clones.
Template creation and read-only profile checks do not certify downstream courses;
their live acceptance remains separate. The walkthrough has not been live-tested.

## Choose a Proxmox course

* `proxmox/provider-bootstrap` — optional NONE-scope guidance for creating a
  named profile.
* `proxmox/nixos-template` — learner-operated template construction, also NONE
  scope.
* `proxmox/proxmox-admin` — provider-backed disposable VM course after a
  working profile exists.

Start the draft provider-bootstrap guidance on the controller with:

```bash
learnlab start proxmox/provider-bootstrap --include-drafts
```

Completion and self-attestation are not provider validation and not live certification.

The following is the complete schema for a named profile. The concrete
resource names below are **Checkpoint 05 example values**, not LearnLab
defaults: replace the API host, token identity, template, node, storage,
network, SSH user, and identity-file path with values for your own profile.
LearnLab has no built-in profile name, VMID, node, storage, network, or API URL.

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
ssh_user = "student"
ssh_identity_file = "~/.ssh/learning-platform"
tls_verify = true
template_capabilities = ["os.nixos", "tool.curl"]
```

Save it as `~/.config/learnlab/config.toml` (or the equivalent XDG path). The
`token_secret_env` value is the *name* of an environment variable, never the
token itself. Set the named secret without placing its value in command history:

```bash
read -r -s LEARNLAB_HOME_PROXMOX_TOKEN_SECRET
export LEARNLAB_HOME_PROXMOX_TOKEN_SECRET
printf '\n'
```

Do not place the secret in shell history, source files, curriculum, TOML,
SQLite, or test files. Prefer a shell session, secret manager, or another
process-level secret mechanism that supplies the profile-specific variable.

TLS certificate verification is on by default: keep `tls_verify = true` for
normal use. Setting `tls_verify = false` is an explicit private-lab exception
and LearnLab warns when it is disabled. Use a certificate trusted by the
controller rather than disabling verification.

Python 3.13's strict certificate validation can reject a legacy/default
Proxmox cluster CA that lacks CA/key-usage X.509 extensions even when curl
accepts it. Curl success therefore does not prove that LearnLab's Python client
will accept the same trust file. The preferred repair is a correctly issued
controller-trusted CA/server certificate with an exact SAN match for the
configured API hostname or IP.

A bounded fallback may pin the current public server leaf certificate as an
explicit trust anchor only after authenticating it through a separate trusted
management path and verifying its expected issuer/chain, exact SAN match for
the configured endpoint, validity window, and SHA-256 fingerprint. Capturing
an unchecked certificate with `openssl s_client` over the same untrusted
connection is not authentication and is never sufficient.

Store the verified public leaf in an owner-only controller file outside the
repository, config TOML, progress/evidence, and secret stores. Export
`SSL_CERT_FILE` in the same dedicated short-lived controller process that runs
`learnlab provider test` or provider-aware validation. It is a process
environment setting, not a ProxmoxProfile field and not the token secret;
`token_secret_env` remains only the name of the separately named token-secret
variable. After the checks, run `unset SSL_CERT_FILE` and separately clear that
token-secret variable. Do not add a profile field for the trust file.

A leaf pin is deliberately rotation-sensitive. Certificate renewal,
replacement, expiry, SAN change, or fingerprint mismatch requires stopping,
re-authenticating the new certificate out of band, and deliberately replacing
the pin. Never silently refresh it or weaken `tls_verify = true`.

The Checkpoint 05 profile also required the token's `SDN.Use` permission scoped
to `/sdn/zones/localnetwork/vmbr0`. That path was an environment-specific
discovery, not a general default: grant only the permissions and resource scope
required by your configured network.

`template_capabilities` declares what the configured template is expected to
provide. These provider-neutral IDs are checked against course requirements;
they are profile assertions and do not probe installed guest software.

## Check and use a profile

The health check is read-only. It validates API access, the selected node and
template, storage, and network, but it cannot prove mutation-only permissions.

```bash
learnlab provider test home-proxmox
```

## Learn through an interactive course session

Start begins a new session or resumes saved local progress. It selects the
first incomplete lesson by default and remains open while it guides you through
each step and its checks:

```bash
learnlab start proxmox/proxmox-admin --provider home-proxmox --include-drafts
```

The packaged courses are currently unproven drafts, including the Proxmox
course. LearnLab requires `--include-drafts` to start any course that is not
`live-validated`. The flag is an explicit choice to exercise uncertified
content; it is not evidence that the course or template has passed live
acceptance. A matching certification record is also invalidated by any course
file change, which returns the effective maturity to `draft`.

You may also resume an existing course explicitly:

```bash
learnlab resume proxmox/proxmox-admin --provider home-proxmox
```

While `start` or `resume` provisions or waits for an environment, LearnLab
emits immediate lifecycle feedback. In an interactive terminal, one spinner
line updates with the current stage, each polling retry attempt, elapsed time,
and the ready result. In non-TTY output, it writes deterministic,
newline-delimited stage messages and retry attempt numbers instead of spinner
animation.

Use `learnlab progress` to view the recorded lesson state. During a session,
press `q` at a verification prompt, or choose save and exit after a lesson, to
persist every completed check and leave safely. Run `start` or `resume` later
to continue at the first incomplete verification; earlier passed checks remain
recorded.

### Environment scopes and safe replacement

Curriculum chooses one environment scope rather than reading provider details
from lesson files:

- `course` creates one disposable environment and reuses it for the course.
- `lesson` gives each lesson its own environment; moving to another lesson
  displays the exact recorded VM and requires confirmation before replacement.
- `none` skips provider configuration and secret resolution entirely.

The included `proxmox/proxmox-admin` course uses `course` scope. Its shared VM
is limited to read-only system inspection; the token lessons are conceptual.
Course content never supplies a provider profile, endpoint, VMID, template,
node, token, or other deployment value.

For any VM scope, LearnLab reuses an environment only after its recorded
profile, provider fingerprint, endpoint, VMID, and expected VM name all match.
A mismatch fails closed and directs you to the destroy/recovery path. A
lesson-scoped replacement is never implicit: declining its confirmation keeps
the existing VM and your progress unchanged.

### Verification progress

Every step has a nonempty, ordered list of verifications. All are required: a
step completes only after every check passes in the order shown. A course can
combine repeated validator types, including the two read-only remote checks and
two read-only provider checks in the included course. The supported types are:

- `remote-command`: runs the curriculum-authored command non-interactively over
  SSH and passes only on exit status zero.
- `text-evidence`: compares your bounded response against a configured exact
  value or regular expression.
- `manual-confirmation`: records a clearly labeled self-attestation; it is not
  objective verification.
- `provider-check`: invokes a named read-only provider inspection and never
  creates, starts, stops, reconfigures, or deletes infrastructure.

LearnLab uses the configured SSH user and identity file with a per-environment
`known_hosts` file, batch mode, and connection and command timeouts. It never
disables host-key checking or writes to your normal SSH host-key database.
Remote commands come from reviewed curriculum and are passed as one remote
argument; LearnLab never turns learner text into a shell command.

### Administrative progress override

`progress complete` is an administrative override for exceptional recovery or
course administration, not the normal learner flow. It asks for confirmation,
records its provenance as `manual_override`, and reports that normal learners
should use `start` or `resume`:

```bash
learnlab progress complete proxmox/proxmox-admin/api-access
```

Deliberate automation can bypass only that confirmation with `--yes`:

```bash
learnlab progress complete proxmox/proxmox-admin/api-access --yes
```

The override does not manufacture validator evidence or turn a self-attestation
into an objective result. Review the recorded provenance when assessing course
progress.

Reset only the desired scope. Reset refuses to proceed if the scope still has
an environment that must first be destroyed:

```bash
learnlab reset proxmox
learnlab reset proxmox/proxmox-admin --yes
```

Destroy is global for the current operating-system user's recorded LearnLab
environments. The interactive form lists targets, asks for confirmation, and
asks whether to preserve completed progress:

```bash
learnlab destroy
```

For non-interactive use, `--yes` requires exactly one explicit progress policy:

```bash
learnlab destroy --yes --preserve-progress
learnlab destroy --yes --erase-progress
```

## Legacy state database recovery

The current state database is `learnlab.db`. If LearnLab finds only the former
default `state.db`, the next state command makes a WAL-aware SQLite backup,
updates the copied schema, atomically installs `learnlab.db`, and preserves the
original as `state.db.migrated`. Keep that backup until the migrated progress,
attempts, and environments have been reviewed. Migration fences legacy writers
while it takes and installs the snapshot. Commands that already had `state.db`
open may then fail with `legacy database migrated; reopen LearnLab`; rerun the
interrupted command so it opens `learnlab.db`.

The preserved `state.db.migrated` rejects inserts, updates, and deletes to its
progress, attempt, and environment rows. Treat it as a read-only recovery copy;
the retirement guards prevent an old process from silently writing ownership
state that is absent from the new authoritative database.

LearnLab stops without changing state when both `state.db` and `learnlab.db`
exist, or when it finds unfinished migration artifacts. Preserve every file,
inspect which database is authoritative, move the other database and artifacts
outside the state directory, and retry only when exactly one authoritative
`learnlab.db` remains. LearnLab never guesses, merges, or overwrites these files.

Historical environment rows do not contain the provider fingerprint or expected
VM name now required for destructive ownership checks. Those fields migrate as
empty, so LearnLab retains the environment and refuses remote stop/delete rather
than guessing ownership. Reconcile such infrastructure manually against the
recorded profile, VMID, node, and provider inventory; preserve the databases
while doing so and never delete a VM solely because its VMID matches.

## Author and validate curriculum

Maintain courses only under `src/learnlab/collections/`. The installed wheel
uses this same canonical tree. Validate the complete catalog or one
`collection/course` without loading settings, state, secrets, SSH, or providers:

```bash
learnlab validate
learnlab validate proxmox/proxmox-admin
learnlab validate proxmox/proxmox-admin --format json
```

Warnings are advisory and exit successfully. Exit code `0` means there are no
curriculum errors, though warnings may be present; `1` means curriculum or
capability errors; `2` means invalid command usage; and `3` means a provider or
operational failure in online mode. Schema-v1 JSON has exactly
`schema_version`, `ok`, and `findings`; each finding has `severity`,
`course_path`, `source_path`, `code`, `message`, and `remedy`.

VM environments may declare optional provider-neutral requirements:

```yaml
environment:
  scope: course
  provider_capability: proxmox.vm
  guest_capabilities:
    - os.nixos
    - tool.curl
```

A lesson environment replaces the whole course policy rather than merging with
it. The legacy top-level `requirements` list is temporarily mapped to
`environment.guest_capabilities`, emits a validation warning, and is planned
for removal. New curriculum should use `guest_capabilities` directly. Never put
profile names, URLs, VMIDs, template names, nodes, storage, networks, SSH paths,
token identities, or secrets in curriculum.

Online validation runs offline checks first, then resolves only the explicit
profile, compares declared capabilities, and invokes the read-only provider
health check:

```bash
learnlab validate proxmox/proxmox-admin --provider home-proxmox
```

It never creates, starts, modifies, or deletes infrastructure. Passing proves
only that declared capabilities match and health checks succeeded; it does not
prove guest contents, live lesson behavior, acceptance, or certification. See
`docs/LearnLab-Course-Authoring-Guide.md` for the full schema and authoring
workflow.

## Live Proxmox acceptance test

Normal tests are offline and must not connect to Proxmox:

```bash
python3.13 -m pytest -m 'not live' -q
```

`tests/live/test_proxmox_lifecycle.py` is intentionally destructive. It uses
the real production provider to allocate a VMID, clone the configured template,
start the VM, discover an IPv4 address, stop it, delete it, and verify it is
absent in `finally`. It runs only when **both** confirmation inputs are present:

```bash
LEARNLAB_RUN_LIVE_PROXMOX=1 LEARNLAB_LIVE_PROFILE=home-proxmox \
  python3.13 -m pytest tests/live -q
```

The named profile must already be configured, and its profile-specific secret
environment variable must already be available to the process. Do not set
`LEARNLAB_RUN_LIVE_PROXMOX=1` unless you intend real VM mutation and have
reviewed the configured profile and cleanup risk.
