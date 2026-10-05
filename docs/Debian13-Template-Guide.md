# Debian 13 template guide — installation, sealing, clone checks and profile

This draft guide covers all seven course lessons. The procedure has not been
live-tested on a target Proxmox node or Debian guest; a passing offline course
check is not an installation result. It assumes Debian 13 (trixie) amd64 netinst,
Python 3.13 on the controller, Q35/OVMF UEFI, one disposable VirtIO SCSI disk,
an ordinary DHCP LAN bridge and a QEMU agent enabled in Proxmox. Record the
exact Debian 13.x ISO, Proxmox version and local choices during an authorized
live run; verify release-specific UI and `qm` behavior on that installation.
LearnLab records
self-attested answers; it does not create or inspect these resources. Start on
the **Controller** with `learnlab start proxmox/debian13-template --include-drafts`
without a provider profile. Keep node, VM IDs, names, storage, bridge, disk,
addresses, keys and passwords in an owner-only worksheet outside LearnLab.
After interruption, reconcile the real Proxmox and guest state with that
worksheet before continuing. An ID by itself never establishes ownership.

## 0. Prerequisites and safe start

**Controller — start the draft course.** Have controller access, an authorized
Proxmox UI/node account, permission to create disposable VMs, ISO/package
sources, DHCP and controller-to-guest SSH reachability, and sufficient disk and
RAM. No profile or template is required to start:

```sh
# Controller
learnlab start proxmox/debian13-template --include-drafts
```

Expected: the course opens with `Environment policy: none` and saves progress
locally. A provider prompt, attempted VM action or inability to open the draft
is a stop condition; check the course path, installed package and draft flag.
Keep a private worksheet of node, storage, bridge, candidate VM ID/name, disk,
two clone identities and planned profile name. Inspect occupied IDs and names
before creating anything; do not delete an occupant to free an ID. After
interruption, inspect actual state first and resume with `learnlab resume
proxmox/debian13-template`. Never enter worksheet values, secrets or raw
fingerprints into LearnLab answers, Git or public reports. All confirmations
are learner attestations; LearnLab does not provision these resources.

## 1. Create the installer VM

**Controller — verify media.** Use the [Debian 13 installer page](https://www.debian.org/releases/trixie/debian-installer/)
over HTTPS. Follow the amd64 netinst link for a specific 13.x release, and
write down the exact ISO filename and revision privately. Use the matching
`SHA256SUMS` and signature from the official image directory. Follow Debian's
[image authentication procedure](https://www.debian.org/CD/verify) and check
the signing key fingerprint independently before trusting the signed sums.
Compute `sha256sum` on the downloaded ISO and compare its complete hash and
filename with the authenticated list. The expected result is an exact match.
If TLS, signature, filename or digest fails, stop before upload. A changing
`stable` URL and an unauthenticated forum checksum are insufficient.

**Proxmox node — inspect, then create.** In the management UI inspect the chosen
node, storage, bridge and occupied VM IDs/names. Pick a new disposable ID and
distinctive name. Upload the verified ISO to ISO-capable storage. When using
the UI's URL download, verify the stored image against the authenticated digest.
The Create VM wizard settings are:

| Wizard page | Setting to inspect |
| --- | --- |
| General | Chosen node, unused ID and name, automatic start off |
| OS | Exact Debian 13 amd64 netinst ISO, Linux guest |
| System | q35, OVMF UEFI, EFI variables disk on chosen storage, VirtIO SCSI single controller |
| Disk | One new SCSI OS disk on chosen storage; size for later package labs |
| CPU and Memory | Compatible CPU type and adequate fixed RAM; 2 vCPU, 2 GiB and 20 GiB disk are examples |
| Network | VirtIO NIC, existing LAN bridge with DHCP and controller SSH path |
| Confirm | Compare every setting and selected identity with the worksheet before creating |

For this lab, disable pre-enrolled Secure Boot keys and confirm that the chosen
installer boots with that firmware choice. Do not weaken shared network policy
to work around DHCP or SSH. Keep the small EFI variables disk distinct from the
OS disk. After creation, set **Options > QEMU Guest Agent** enabled and boot
order ISO first, OS disk second. Inspect Hardware and Options again. The agent
will not respond until installed inside Debian. A wrong ID, disk, storage or
bridge is a stop condition; correct only the known candidate.

**Installer console — boot and check network.** Start the inspected candidate
and select text-mode **Install**. Expect the Debian Installer menu under UEFI.
A firmware shell suggests ISO attachment/boot order; a security violation
suggests Secure Boot configuration. Select language and keyboard; inspect the
DHCP address, gateway, resolver and temporary hostname. The installer should
reach an online Debian mirror. With no link/address, inspect Proxmox NIC/bridge
and DHCP. With address but no mirror, inspect route, DNS, time and HTTPS. An
installer shell can run read-only `ip address`, `ip route`,
`cat /etc/resolv.conf` and `date`; keep output private. Stop before partitioning
until firmware and network are understood.

## 2. Install Debian 13

**Installer console — set up the base system.** Confirm the installed target is
the disposable VM, not the controller. Choose locale, keyboard, time zone,
DHCP hostname and online trixie mirror. Choose a local learner account and
console recovery route. Debian Installer's account choice matters: setting a
root password enables root console login and may leave the first user without
sudo; leaving it empty disables direct root login and makes the first user an
administrator. Keep every password private. A mirror error calls for checking
DHCP, DNS, clock and the mirror before any disk change.

**Installer console — identify the disk before writing.** Choose **Manual
partitioning**. Inspect the displayed disk model, size, existing signatures
and partitions; compare them with Proxmox Hardware and the private worksheet.
Do not infer the target from `/dev/sda` or a VMID. On the confirmed disposable
OS disk, use GPT, a 1 GiB EFI System Partition at `/boot/efi` and the remainder
as ext4 `/`. Leave swap out of this disposable baseline only with adequate RAM.
Before **Finish partitioning and write changes to disk**, review the installer's
entire proposed write summary and explicitly confirm that only the selected
OS disk is affected. If there is a wrong disk or no ESP, choose No and stop.
There is deliberately no copyable formatting command before that decision.

**Installer console — finish and boot from disk.** Install the base system,
select **SSH server** and **standard system utilities**, and deselect desktop
environments. Confirm GRUB EFI installation using the intended ESP. Package
download errors require mirror/network checks; GRUB errors require UEFI/ESP
checks. Neither is a completed install. After success, detach the ISO in
Proxmox and place the OS disk first in boot order. Expect a Debian login
prompt. If the installer or UEFI shell returns, inspect boot order, ISO,
EFI variables disk and GRUB before trying to reinstall.

**Installed guest — verify.** At the console inspect `cat /etc/os-release`,
`findmnt /`, `findmnt /boot/efi`, `test -d /sys/firmware/efi && echo UEFI`,
and `lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS`. Expect `ID=debian`, major
`VERSION_ID=13`, ext4 root, mounted ESP and UEFI disk boot. Any mismatch is a
stop condition; investigate the disk actually booted. These are local learner
observations, not remote LearnLab checks.

## 3. Configure lab access

**Installed guest — packages and network.** First inspect `/etc/os-release`,
`/etc/apt/sources.list` and `/etc/apt/sources.list.d/`. A working online trixie
source must replace any installation-media-only `cdrom:` source. Check IP,
route and DNS before running `apt update`. From the root console or existing
sudo route, install `openssh-server qemu-guest-agent sudo curl nftables iproute2
python3 coreutils passwd`. If apt asks for media or fails, check sources,
network, DNS, clock and TLS before proceeding. Keep nftables inactive without
default-deny rules; firewall exercises belong downstream.

**Proxmox node and installed guest — agent.** Confirm the Proxmox QEMU Guest
Agent option and inspect `systemctl status qemu-guest-agent` in the guest. The
unit can be static; inability to enable it is not failure when it is active.
Expect a current agent response/IP in Proxmox. Otherwise inspect the option,
guest package, virtio serial channel and `journalctl -u qemu-guest-agent`.

**Controller and installed guest — SSH trust.** Locate or generate a protected
controller key pair. Only its public key goes into the intended guest account's
`authorized_keys`; keep the private key on the controller. Before creating an
account, set `LAB_USER` locally with `read -r LAB_USER` and run
`getent passwd "$LAB_USER"` for that exact name. Inspect the local file with
`awk -F: -v name="$LAB_USER" '$1 == name {print $0}' /etc/passwd`, and check
`getent passwd root` as a basic lookup control. A missing result alone is not
proof of absence. If a local entry exists but lookup fails, or NSS times out or
reports errors, inspect `/etc/nsswitch.conf` and relevant service logs; stop
until lookup health is understood. Use `/usr/sbin/useradd` only for a truly
absent account that the local account plan calls for. Check home ownership,
`~/.ssh` mode 700 and `authorized_keys` mode 600.

At the **installed guest's Proxmox console**, run
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` and retain the SHA256
fingerprint privately. On the **controller**, select local values for
`GUEST_ADDR` (observed guest address), `KEY_FILE` (protected private-key path),
`LAB_USER` and a *new* owner-only `KNOWN_HOSTS` file distinct from your global
SSH store. Use `read -r GUEST_ADDR`, `read -r KEY_FILE`, `read -r LAB_USER`
and `read -r KNOWN_HOSTS` locally to populate them. `test ! -e "$KNOWN_HOSTS"`
must pass; otherwise choose a new path and do not overwrite the old file.
Set `umask 077`, run
`ssh-keyscan -T 5 -t ed25519 "$GUEST_ADDR" > "$KNOWN_HOSTS"`, then
`ssh-keygen -lf "$KNOWN_HOSTS"`. Compare the fingerprint exactly with the
console result **before** trusting the captured key. A mismatch or missing key
is a stop condition; `ssh-keyscan` alone does not establish trust. After the
match, test a fresh key-only login with strict checking:

```sh
# Controller; use locally chosen variables, never paste their values into LearnLab.
ssh -o UserKnownHostsFile="$KNOWN_HOSTS" \
    -o GlobalKnownHostsFile=/dev/null \
    -o StrictHostKeyChecking=yes \
    -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no \
    -o PreferredAuthentications=publickey \
    -i "$KEY_FILE" "$LAB_USER@$GUEST_ADDR" id -un
```

Expect the chosen account name and no host-key warning. A hidden **local**
prompt to unlock the protected private key is allowed; a guest-account
password prompt is not.
Keep the Proxmox console available. On failure inspect account, permissions,
ssh.service, network and logs; do not disable password authentication yet.

**Installed guest — lab sudo and recovery.** In a root console, interactively
write `/etc/sudoers.d/learnlab-lab` for this disposable guest. Replace
`LAB_USER` in the following example with the exact chosen account name; do not
leave the placeholder in the real file:

```sudoers
LAB_USER ALL=(root) NOPASSWD: ALL
```

This deliberately broad **lab-only** root rule supports the downstream apt,
nftables, account and systemd exercises. Set owner/group `root:root` and mode
`0440` with `chown root:root /etc/sudoers.d/learnlab-lab` and
`chmod 0440 /etc/sudoers.d/learnlab-lab`; inspect with
`stat -c '%U:%G %a' /etc/sudoers.d/learnlab-lab`. Validate
with `/usr/sbin/visudo -cf /etc/sudoers.d/learnlab-lab` and
`/usr/sbin/visudo -c` before closing the root console. From a fresh controller
key session, inspect `sudo -n -l` for the root ALL rule. Run `sudo -n true`,
`sudo -n id -u`, `sudo -n apt --version`, `sudo -n nft --version` and
`sudo -n systemctl --version`; expect no password prompt, uid 0 and successful
read-only version checks. A failure requires console repair, ownership and
`sudo -l` inspection. Retain a separate administrator console route. Only
after key and sudo checks may you optionally change password SSH settings;
inspect effective `sshd -T`, reconnect in a second session, then end the first.
This broad rule is unsuitable as a default for production hosts.

The downstream courses currently requiring `os.debian.13` request these
capabilities. Verify the commands in the guest; declaring a capability in a
future profile does not install it:

| Capability | Command and source |
| --- | --- |
| `os.debian.13` | `/etc/os-release` with ID and major VERSION_ID checked above |
| `tool.apt`, `tool.dpkg` | `apt`, `dpkg` from Debian's package base |
| `tool.coreutils`, `tool.timeout` | `ls`, `timeout` from `coreutils` |
| `tool.curl` | `curl` from `curl` |
| `tool.ip` | `ip` from `iproute2` |
| `tool.nft` | `nft` from `nftables`, with no base firewall rules |
| `tool.python3` | `python3` from `python3` |
| `tool.sudo` | `sudo` from `sudo` |
| `tool.useradd` | `/usr/sbin/useradd` from `passwd` |
| `tool.journalctl`, `tool.systemctl`, `tool.systemd`, `tool.systemd-run` | `journalctl`, `systemctl`, PID 1 systemd, `systemd-run` from Debian systemd packages |

Do not add nginx sites, firewall exercise state, downstream exercise units or capstone
artifacts to this base guest. The bootstrap course itself remains environment
scope `none` with no managed guest or provider checks.

## 4. Seal and convert the candidate

**Proxmox node — inspect.** Recheck that the installed candidate passes the
console, key SSH, sudo, tool and guest-agent checks above. Compare its node,
VMID, name, disk/storage, power state and template flag with the private
owner-only worksheet. Inspect its snapshot tree. Do not mutate a working
template or one used by another profile. Keep a recoverable original/source
until two clones pass. If none exists, make a separate backup or full source
clone before sealing, budget its storage and verify ownership/recoverability.
Snapshots block conversion; preserve
them and diagnose, without automatic deletion or force. On resume inspect
whether the candidate is running, partly sealed, off or already a template.
Booting after sealing can regenerate identity and invalidates that seal.

**Installed guest administrator console — configure missing SSH keys.** Keep
console recovery open. Inspect `systemctl cat ssh.service`, `systemctl cat
ssh.socket`, `systemctl is-enabled ssh.service ssh.socket`, `systemctl
is-active ssh.service ssh.socket`, `systemctl list-sockets`,
`sshd -T` hostkey paths, `ls -l /etc/ssh/ssh_host_*_key*` and
`findmnt -T /etc/ssh`. Absent ssh.socket is fine. A masked service or unclear
activation path is a stop condition; do not unmask silently. Stop on custom
host-key paths, symlinks, unexpected file types or mounts until resolved.
As root, interactively create
`/etc/systemd/system/learnlab-ssh-host-keys.service`:

```ini
[Unit]
Description=Generate missing Debian SSH host keys before ssh.service
Before=ssh.service

[Service]
Type=oneshot
ExecStart=/usr/bin/ssh-keygen -A
TimeoutStartSec=30s
RemainAfterExit=yes
```

Create `/etc/systemd/system/ssh.service.d/10-learnlab-host-keys.conf`:

```ini
[Unit]
Requires=learnlab-ssh-host-keys.service
After=learnlab-ssh-host-keys.service
```

Set both root:root mode 0644. Run `systemctl daemon-reload`; get the actual
SSH unit path with `systemctl show ssh.service -p FragmentPath`, then run
`systemd-analyze verify` on that path and the new unit. Inspect `systemctl
cat ssh.service` and `systemctl show ssh.service -p Requires -p After`;
resolve relevant errors or absent dependency. Before disabling an enabled or
active ssh.socket, inspect ssh.service's `[Install]` section and boot path.
If service is startable but disabled, explicitly confirm `systemctl enable
ssh.service`; verify `systemctl is-enabled ssh.service` reports enabled and
inspect its boot-target link. A masked, static or unenableable service without
a verified boot trigger means stop; do not unmask or assume SSH will start.
Inspect the socket's triggers; explicitly confirm `systemctl disable
ssh.socket` only after the service boot path is verified. Stop the socket at
sealing. Before
deleting any key, privately record `ssh-keygen -lf
/etc/ssh/ssh_host_ed25519_key.pub`, run `systemctl start
learnlab-ssh-host-keys.service` and compare that fingerprint again. Expected:
unchanged. Debian trixie's [ssh-keygen manual](https://manpages.debian.org/trixie/openssh-client/ssh-keygen.1.en.html)
confirms `-A` creates only missing default host keys. The unit deliberately
has no `ConditionFirstBoot=yes`: [machine-id(5)](https://manpages.debian.org/trixie/systemd/machine-id.5.en.html)
says an existing empty `/etc/machine-id` gets a new ID but does not count as
first boot. `Requires=` plus `After=` makes failed generation block SSH.

**Installed guest administrator console — inspect identities.** Run `stat -c
'%F %n' /etc/machine-id /var/lib/dbus/machine-id`, `ls -l
/var/lib/dbus/machine-id`, `readlink /var/lib/dbus/machine-id` if it is a
symlink, and `findmnt -T` on each path. Confirm actual types and writable
guest filesystems and `/etc/machine-id` as an ordinary file. A verified
D-Bus symlink to `/etc/machine-id` stays intact. A separate regular D-Bus
file must not remain empty: systemd can fall back to its old value, while
D-Bus may reject an empty file. After exact type, parent and mount checks,
plan to replace only that file with a symlink to `/etc/machine-id` so both
read the new clone ID. Unexpected targets, mounts, missing parents or types
require diagnosis. Inspect the active DHCP client with
`systemctl status systemd-networkd NetworkManager networking`, `ps -ef`, its
config and logs. For ifupdown/dhclient, inspect `/etc/network/interfaces`,
dhclient configuration and `/var/lib/dhcp/` leases; identify only leases for
this interface before clearing individually. For NetworkManager inspect the
connection's DHCP ID policy and per-connection leases; for systemd-networkd
inspect ClientIdentifier policy and runtime leases. Clear only proven
persistent per-machine state of the active client. Do not copy a generic
cleanup recipe. Both clones later verify DHCP identity uniqueness.

**Installed guest administrator console — confirm, execute, verify.** Confirm
candidate ownership, source and every file individually. Recheck that
`systemctl is-enabled ssh.service` reports enabled. Stop ssh.socket if present
and ssh.service; confirm the socket is disabled/inactive and SSH cannot restart
before shutdown. Remove
only the inspected ordinary `/etc/ssh/ssh_host_*_key` private/public pairs,
one named pair at a time; keep authorized_keys and controller keys. For a
verified ordinary `/etc/machine-id`, use `: > /etc/machine-id` as root and
verify it is empty. If `/var/lib/dbus/machine-id` was a separately verified
ordinary file on the expected writable filesystem, confirm that exact path
again, run `rm -- /var/lib/dbus/machine-id` as root, then
`ln -s -- /etc/machine-id /var/lib/dbus/machine-id`. Check
`test -L /var/lib/dbus/machine-id` and that
`readlink /var/lib/dbus/machine-id` reports exactly `/etc/machine-id`.
Leave a pre-existing verified symlink untouched. If interrupted between
removal and link creation, reinspect before making the link; do not reboot
with the D-Bus path absent. Reinspect the selected paths and keys, then run
`systemctl poweroff`. **Do not reboot** or
restart SSH after sealing. A partial seal needs fresh inspection before any
repeat.

**Proxmox node — convert.** Reinspect exact ID/name/node/disk, stopped state,
no snapshots, no template flag and retained source. Explicitly confirm
Convert to template in the UI for that candidate. Expected: a stopped
template and intact source. On snapshot or other task error, inspect state;
do not force conversion, delete snapshots or boot the template to test it.

## 5. Accept two full clones

**Proxmox node — inspect and create.** Reserve two unused IDs and distinct
names privately. Check occupancy, exact template identity, storage and
network. A failed lookup does not prove absence. For each choose Clone >
**Full Clone**, inspect source/target/node/storage, explicitly confirm and
wait for successful completion. Check each disk, NIC MAC, EFI/firmware
identity and VM flag; A and B must have distinct Proxmox-generated MAC and
firmware identities. Stop on a collision before network boot. Remove installer
ISO, boot both from disk, and retain template and source.

**Installed guest console — check each boot.** On A, then B, confirm Debian
13 in `/etc/os-release`, disk boot, DHCP address/route and actual DHCP client
identity. Check `systemctl status qemu-guest-agent` and a current Proxmox
agent response. Inspect `systemctl status learnlab-ssh-host-keys.service
ssh.service`, `systemctl show ssh.service -p Requires -p After`, and
`systemctl cat ssh.service`. Verify `systemctl is-enabled ssh.service` reports
enabled, `systemctl is-active ssh.service` reports active and ssh.socket is
disabled/inactive. Missing keys should have been generated before SSH. A
masked, disabled or inactive service fails the boot path; do not unmask it
silently. If keys, dependency or service are missing, use `journalctl -u
learnlab-ssh-host-keys.service -u ssh.service` and stop. Verify online trixie
apt sources, package/service state and all required tools in the table above
on **both** clones.

**Guest console and controller — authenticate SSH.** On each clone's trusted
console run `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` and keep its
fingerprint privately. On the controller choose local `GUEST_ADDR`,
`LAB_USER`, `KEY_FILE` and a *new* owner-only `KNOWN_HOSTS` path for that
clone. Set each with `read -r`. `test ! -e "$KNOWN_HOSTS"` must pass. With
`umask 077`, run `ssh-keyscan -T 5 -t ed25519 "$GUEST_ADDR" > "$KNOWN_HOSTS"`
and `ssh-keygen -lf "$KNOWN_HOSTS"`. Compare with **that clone's** console
fingerprint; ssh-keyscan alone is not trust. Stop on mismatch. Do not remove
global known_hosts entries because DHCP reused an address. Only after a
match, use the strict SSH command in section 3 with the per-clone variables;
expect the chosen account name. That command ends the SSH session. Check
sudo with a separate remote command using the same strict options:

```sh
# Controller; use the variables and authenticated host key for this clone.
ssh -o UserKnownHostsFile="$KNOWN_HOSTS" \
    -o GlobalKnownHostsFile=/dev/null \
    -o StrictHostKeyChecking=yes \
    -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no \
    -o PreferredAuthentications=publickey \
    -i "$KEY_FILE" "$LAB_USER@$GUEST_ADDR" sudo -n true
```

Both commands must succeed. A local private-key unlock is allowed; a guest
password prompt is a failure. Repeat independently for B.

**Guest console — compare and reboot.** Privately inspect nonempty
`/etc/machine-id`, then verify `test -s /etc/machine-id`, the D-Bus path's
`readlink` target is exactly `/etc/machine-id`, and `cmp -s /etc/machine-id
/var/lib/dbus/machine-id` succeeds. Query the running bus with `busctl
--system call org.freedesktop.DBus / org.freedesktop.DBus.Peer GetMachineId`
and compare its ID locally with `/etc/machine-id`; a failed call or mismatch
blocks acceptance. Check fingerprints of every
`/etc/ssh/ssh_host_*_key.pub` on A and B. Machine IDs and host keys
must be distinct between clones, as must MAC/firmware and persistent DHCP
client identifiers. Reboot **each clone once**, never the template; each
clone's own machine ID and keys must stay stable; repeat the D-Bus link,
file equality and live bus query. Repeat console-authenticated host-key
comparison, both strict SSH commands above (`id -un` and remote
`sudo -n true`), and agent and tool checks. Shared or changed identity,
lost service or access blocks acceptance. Keep raw IDs, fingerprints and
addresses out of LearnLab, Git and reports; record only local pass/fail.
Retain both test clones for the later provider/cleanup lesson. They are
learner-owned; `learnlab destroy` cannot remove them.

## 6. Configure the provider and reconcile test clones

**Controller — add a named profile.** Prerequisite: both full clones passed
disk boot, SSH, sudo, guest agent, tool and identity checks, including stable
identity after each reboot. Reconcile the worksheet and real Proxmox state on
resume. In `~/.config/learnlab/config.toml`, or
`$XDG_CONFIG_HOME/learnlab/config.toml` if set, add a new
`[providers."CHOSEN_PROFILE"]` table in a local editor. Keep an owner-only
backup outside Git; preserve other profiles and an existing `default_provider`.
If this is a new config, add top-level `default_provider = "CHOSEN_PROFILE"`
before the table. Replace every example below with independently verified local
values; there are no LearnLab defaults for them:

```toml
# Controller: illustrative field shapes, never paste actual values into LearnLab
[providers."CHOSEN_PROFILE"]
type = "proxmox"
api_url = "https://pve.example:8006"
token_id = "account@pve!token"
token_secret_env = "LEARNLAB_TEMPLATE_TOKEN_SECRET"
template_vmid = 9001
template_name = "debian-13-template"
node = "pve-node"
storage = "local-lvm"
network = "vmbr0"
ssh_user = "lab-user"
ssh_identity_file = "~/.ssh/lab-key"
tls_verify = true
template_capabilities = ["os.debian.13", "tool.apt", "tool.coreutils", "tool.curl", "tool.dpkg", "tool.ip", "tool.journalctl", "tool.nft", "tool.python3", "tool.sudo", "tool.systemctl", "tool.systemd", "tool.systemd-run", "tool.timeout", "tool.useradd"]
```

The table name is the new profile name. `type` selects Proxmox. `api_url` is
the HTTPS API origin with no credentials or API path. `token_id` identifies the
existing API account/token; `token_secret_env` names an environment variable
and never stores the secret. `template_vmid` and `template_name` must both match
the inspected template. `node`, `storage` and `network` select actual placement
for later managed clones. `ssh_user` is the clone-tested account and
`ssh_identity_file` is its controller private-key path. `tls_verify` remains a
true TOML boolean. The capabilities array is the effective union required by
`nginx/nginx-basics`, `nftables-debian13/nftables-basics` and
`systemd-debian/service-authoring`; it is an assertion of the verified guest,
not an installer or probe. On **both** clones, check Debian 13 plus `apt`,
`dpkg`, `curl`, `ip`, `nft`, `python3`, `sudo`, `useradd`, `timeout`, coreutils,
and the systemd commands `systemctl`, `systemd-run`, `journalctl`. Packages
are respectively apt, curl, iproute2, nftables, python3, sudo, passwd,
coreutils and systemd, as checked in section 3. If a tool is absent, repair
and retest the guest; adding its string cannot make it available.

Use a scoped existing token or follow the operator's [Proxmox user and token
guide](https://pve.proxmox.com/pve-docs/pveum.1.html) with the administrator.
Inspect user/token ACLs before changing them; do not silently broaden rights.
The NONE-scope `proxmox/provider-bootstrap` course is optional account setup
guidance. The VM-scoped `proxmox/proxmox-admin` course is not a prerequisite.

**Controller — read-only checks.** In a dedicated short-lived shell, enter the
new profile name and its uniquely named token secret from a manager or hidden
prompt. The example variable must match your actual `token_secret_env`. Keep
the value out of arguments, tracing, history, TOML and LearnLab answers:

```bash
# Controller
read -r PROFILE
read -r -s LEARNLAB_TEMPLATE_TOKEN_SECRET
export LEARNLAB_TEMPLATE_TOKEN_SECRET
printf '\n'
```

Prefer a correctly issued, controller-trusted CA/server certificate whose SAN
matches `api_url`; keep `tls_verify = true`. If Python 3.13 rejects a legacy
CA and a current leaf must be pinned, first authenticate that public leaf
through an independent trusted management path and verify issuer/chain, exact
SAN, validity and SHA-256 fingerprint. Store it owner-only outside Git, TOML,
secrets and evidence. An unchecked `openssl s_client` capture over the same
untrusted connection cannot establish trust. Only then, in the **same shell**
as every provider command, set the process-only override:

```sh
# Controller: only for a separately authenticated trust file
SSL_CERT_FILE="OWNER_ONLY_VERIFIED_SERVER_LEAF_PATH"
export SSL_CERT_FILE
```

Any new shell used for a provider command must establish the same authenticated
trust first. On leaf replacement, expiry, SAN or fingerprint change, stop and
re-authenticate it independently; never silently refresh the pin or disable
TLS verification. Run each command separately and review exit status/output:

```sh
# Controller
learnlab provider test "$PROFILE"
learnlab validate nginx/nginx-basics --provider "$PROFILE"
learnlab validate nftables-debian13/nftables-basics --provider "$PROFILE"
learnlab validate systemd-debian/service-authoring --provider "$PROFILE"
```

Expected: provider health reports PASS for API, node, template, storage and
network; each validation exits 0 with no errors. Draft warnings do not grant
certification. Missing profile or secret means inspect only local names/types;
TLS failure means check independently authenticated trust, SAN and clock; API
denial means inspect existing user/token ACL scope with the administrator;
wrong resource means compare full identity against the worksheet; missing
capability means return to both clone checks. Stop on unresolved findings.
These are read-only health and declared compatibility checks. They do not
prove clone, start or delete permissions or live course success. Finish the
dedicated shell by clearing both variables separately, using your chosen token
name:

```sh
# Controller
unset SSL_CERT_FILE
unset LEARNLAB_TEMPLATE_TOKEN_SECRET
```

**Proxmox node — cleanup, one clone at a time.** These two full clones are
learner-owned and untracked; `learnlab destroy` cannot remove them. Keep the
template, recoverable source and any original working template. Use the private
worksheet and refreshed authorized cluster inventory to match each clone's
node, name, ID, creation history, disk volumes, MAC and firmware identity.
VMID alone is never sufficient. Stop on any discrepancy or failed lookup.
For the first fully identified clone, inspect on its owning node:

```sh
# Proxmox node: inspect one clone
read -r CLONE_VMID
qm config "$CLONE_VMID"
qm status "$CLONE_VMID"
```

Expected: the intended full clone, attached disks, no template flag and known
state. Separately confirm its shutdown. If running, request a graceful shutdown
in the UI or run `qm shutdown "$CLONE_VMID"`; wait for a successful task and
verify Stopped in UI and `qm status`. Timeout or denied lookup is not proof.
Reinspect full identity and get a second, explicit confirmation to destroy that
exact clone and its disposable attached disks. Use UI Remove or:

```sh
# Proxmox node: after separate destruction confirmation
qm destroy "$CLONE_VMID"
```

Do not add force, purge, skiplock or unreferenced-disk options. Expected:
successful removal task, absence from a successfully refreshed authorized
cluster inventory and absence of its recorded attached volumes; retained
template and source still present. A failed `qm config` lookup alone cannot
prove absence. On uncertainty, stop, retain the worksheet and reconcile with
the administrator. Never retry deletion by VMID alone. Repeat every identity,
shutdown, destruction and absence check independently for the second clone.
Record only non-secret pass/fail. Course completion records self-attested
progress, while live template acceptance and downstream certification require
separate authorization and exact-digest evidence.

## Primary references and live boundary

The procedure follows the [Debian 13 amd64 installation guide](https://www.debian.org/releases/trixie/amd64/),
[trixie installer media](https://www.debian.org/releases/trixie/debian-installer/),
[machine-id manual](https://manpages.debian.org/trixie/systemd/machine-id.5.en.html),
[ssh-keygen manual](https://manpages.debian.org/trixie/openssh-client/ssh-keygen.1.en.html)
and [Proxmox qm reference](https://pve.proxmox.com/pve-docs/qm.1.html).
The Proxmox `qm` endpoint was unavailable to this offline authoring pass; its
target-version behavior remains a live verification item. No Proxmox, SSH or
guest command in this guide was executed against a real resource in this task.
