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

The Checkpoint 05 profile also required the token's `SDN.Use` permission scoped
to `/sdn/zones/localnetwork/vmbr0`. That path was an environment-specific
discovery, not a general default: grant only the permissions and resource scope
required by your configured network.

## Check and use a profile

The health check is read-only. It validates API access, the selected node and
template, storage, and network, but it cannot prove mutation-only permissions.

```bash
learnlab provider test home-proxmox
```

Start the included course and select a lesson at the prompt:

```bash
learnlab start proxmox/proxmox-admin --provider home-proxmox
```

When a lesson is complete, record it explicitly:

```bash
learnlab progress complete proxmox/proxmox-admin/api-access
```

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
