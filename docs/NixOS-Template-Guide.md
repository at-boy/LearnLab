# NixOS 26.05 Template Guide

Draft: documentation-reviewed, not live-tested. This guide covers installer creation, installation, lab access, sealing, conversion and two-clone acceptance. Provider handoff and final cleanup are later course tasks. Do not treat these checkpoints as template certification.

LearnLab runs on the controller with `learnlab start proxmox/nixos-template --include-drafts`, without a provider profile. It displays instructions and saves local self-attestations; the learner operates all infrastructure explicitly. A saved answer never establishes current resource ownership.

Prerequisites: permission to create disposable VMs, trusted Proxmox management UI/console access, enough free storage/RAM, existing LAN bridge with DHCP, reachable official ISO/package sources and controller-to-guest SSH. Keep an owner-only worksheet outside this repository with chosen node/storage/bridge, candidate and eventual clone IDs/names, disk identity, template/profile names and private paths. Never paste secrets, personal infrastructure values or raw identities into LearnLab or shared reports. Inspect occupied IDs/names; select another or investigate collisions without deleting anything.

Terminal labels distinguish Controller, Proxmox node, Installer console and Installed guest. Execute each command individually in the labeled location and inspect its result. Installer editors and password prompts are deliberately interactive. Before any destructive action, reconcile full resource identity and repeat the local checkpoint, including after resume.

## Create the Installer VM

### Select and verify the official installer

Controller: prerequisite is the private worksheet and permission to create
a disposable VM. On resume, inspect your existing ISO and VM before downloading
or creating anything again. This draft walkthrough has not been live tested.
Open https://nixos.org/download/ over HTTPS. Under Minimal ISO image choose
64-bit Intel/AMD (x86_64), release 26.05, not ARM or a graphical ISO. Follow
the official channels.nixos.org link to its resolved release artifact. Record
that exact filename/revision and URL locally; a moving channel URL alone is
insufficient. Obtain the matching SHA-256 checksum from that same official
release directory over HTTPS. Do not substitute a checksum from a forum.
Save both locally. In a controller terminal, enter the actual downloaded ISO
path into ISO_PATH using `read -r ISO_PATH`, then run `sha256sum "$ISO_PATH"`.
Compare the entire digest with the official digest and the filename/revision
with the intended image. A checksum catches damaged/mismatched downloads;
HTTPS and the official source establish where the expected digest came from.
Expected: exact match and a 26.05 minimal x86_64 artifact. On any mismatch,
missing checksum, unexpected redirect or TLS failure, stop before upload;
recheck the official release and download. Never disable TLS verification.

Local checkpoint: Confirm locally that the official ISO revision and full checksum match; do not paste them here.

### Explain the media integrity check

Controller: the checksum comparison checks that the downloaded bytes match
the expected official artifact. This concept answer is not ISO verification.

### Create and inspect a new candidate

Proxmox node (management UI): inspect the chosen node, available storage and
existing IDs/names. Reserve a new VM ID and distinctive candidate name in
your owner-only worksheet. Existing or ambiguous identity means stop and
inspect or choose another; never delete a VM to make the ID available.
Upload the verified ISO to storage supporting ISO images. If using Download
from URL instead, supply the exact official URL and verified SHA-256 in the
UI, and require successful verification before using that upload.
Create VM: General = chosen node, unused ID and chosen name; OS = verified ISO,
Linux guest type; System = Q35 machine, OVMF (UEFI) BIOS, EFI disk on selected
storage (4m EFI type), and VirtIO SCSI single controller. Disable Pre-Enroll keys / Secure
Boot for this installer; an unsigned installer may be rejected by Secure Boot.
This deliberate lab firmware choice is not production hardening. Keep the
EFI variables disk distinct from the single OS data disk. Disk = one new SCSI
disk on selected storage, capacity chosen for downloads/builds. CPU = a type
compatible with intended nodes and adequate cores. Memory = adequate fixed
RAM for installation/builds. 2 vCPU, 2 GiB RAM and 20 GiB disk are illustrative
starting sizes, not defaults or a guarantee; allocate more if needed.
Network = VirtIO NIC, your existing ordinary LAN bridge with DHCP; no new
VLAN, SDN or cloud-init drive. Check local firewall policy permits DHCP and
controller SSH. Do not disable shared network protections as a workaround.
Confirm page: leave automatic startup unchecked and inspect all settings.
After creation, Options -> QEMU Guest Agent = enabled; boot order = ISO first
for installation, chosen SCSI disk next. Inspect Hardware and Options against
the worksheet, including storage volume, MAC and disk size; VMID alone does
not establish ownership. No guest-agent response is expected until the guest
service is installed. If storage, firmware or network differs, stop and
correct this new candidate's settings before booting it.

Local checkpoint: Confirm that you inspected the new candidate and matched its hardware and ownership locally.

### Boot the minimal installer and diagnose connectivity

Proxmox node (management UI): start only the inspected candidate and open its
console. Expected: the NixOS minimal installer shell. A firmware shell means
inspect ISO attachment and boot order; a security violation means inspect the
deliberate Secure Boot choice. Stop if this is another VM or release.
Installer console: obtain a root shell with `sudo -i`. Run these read-only
checks, one at a time; keep output and addresses local:

```sh
# Installer console
nixos-version
test -d /sys/firmware/efi && echo UEFI
ip -br link
ip -br address
ip route
getent hosts cache.nixos.org
curl --fail --show-error --location --max-time 30 https://cache.nixos.org/nix-cache-info
```

Expected: 26.05, UEFI, an UP non-loopback NIC with DHCP address, a usable
default route, resolved cache address and HTTPS cache metadata without TLS
errors. No link/address: inspect NIC/bridge/cable-connected and DHCP service.
Address but no route: inspect DHCP/router. Route but failed lookup: inspect
resolver configuration. DNS works but HTTPS fails: inspect clock with `date`,
egress policy and TLS trust. Do not format until all checks pass. Stop and
record the last confirmed phase locally if network or firmware stays wrong.

Local checkpoint: Confirm that the intended installer has UEFI, DHCP, route, DNS and verified HTTPS access.

## Install NixOS on the Verified Disk

### Identify the disk before any writes

Installer console: prerequisite is the verified 26.05 minimal x86_64 installer,
UEFI boot and working network. On resume inspect the VM, mounts and disk
signatures first; an already installed system must not be reformatted.
Reconcile Proxmox node, name, ID, new storage volume and configured size with
the local worksheet. In the root installer shell inspect:

```sh
# Installer console
lsblk -o NAME,PATH,SIZE,MODEL,SERIAL,TYPE,FSTYPE,MOUNTPOINTS
findmnt
read -r INSTALL_DISK
lsblk -o NAME,PATH,SIZE,MODEL,TYPE,FSTYPE,MOUNTPOINTS "$INSTALL_DISK"
wipefs --no-act "$INSTALL_DISK"
```

At the read prompt type the observed whole-disk path, never a guessed /dev/sda
or a partition. Match size/model and parent-child layout to the new virtual
disk. The ISO is read-only optical media; the EFI variables disk is firmware
state, not the OS target. Expected: exactly the intended disposable OS disk,
no mounted child partitions and no unexplained filesystem signatures.
Unexpected data, extra disks, missing disk or any ownership doubt: stop;
recheck the VM Hardware view and worksheet. A path or VMID alone is not proof.
Destructive checkpoint: partitioning and formatting erase the selected disk.
Before proceeding, explicitly confirm to yourself in the VM console the full
observed disk path, size and that its data may be destroyed. LearnLab records
only your attestation; it does not inspect or write the disk.

Local checkpoint: Confirm locally that the exact disposable disk was inspected and its destruction is authorized.

### Create GPT, EFI and root filesystems interactively

Installer console: only after the preceding identity/destruction checkpoint,
launch `cfdisk "$INSTALL_DISK"`. This is an interactive disk editor, not a
validation command. Select GPT only for the confirmed empty target. Create
a 1 GiB first partition of type EFI System, then a Linux filesystem partition
occupying the remaining space. Review the device banner, both sizes and
types before selecting Write and typing its requested confirmation. If the
target or proposed layout differs, Quit without writing and stop.
Re-run `lsblk -o NAME,PATH,SIZE,TYPE,FSTYPE,MOUNTPOINTS "$INSTALL_DISK"`.
Identify both resulting partition paths from output; NVMe-style suffixes
differ from SCSI paths, so do not concatenate a digit onto the disk variable.
If the kernel has not refreshed the layout, stop and inspect before formatting.
Formatting is destructive too: confirm each observed partition's parent,
size, type and absence of mounts immediately before typing its format command.
Type `mkfs.fat -F 32` followed by a space and the verified EFI partition path;
separately type `mkfs.ext4` followed by a space and the verified root partition
path. No pre-filled formatting command is provided: choose each target only
after inspection. Expected: successful filesystem creation, FAT on the small
EFI partition and ext4 on root. Any busy-device/error/unexpected signature
warning means stop; never add force flags to make it proceed.
Enter the observed root and EFI partition paths at these two read prompts:

```sh
# Installer console
read -r ROOT_PART
read -r EFI_PART
mount "$ROOT_PART" /mnt
mkdir -p /mnt/boot
mount "$EFI_PART" /mnt/boot
findmnt /mnt
findmnt /mnt/boot
lsblk -f "$INSTALL_DISK"
```

Expected: selected ext4 root at /mnt and FAT EFI at /mnt/boot. Inspect each
command's result before continuing; do not generate configuration with a
missing/wrong mount. After interruption re-identify paths and mounts; do not
repeat partitioning or formatting on an installed or partly installed disk.

Local checkpoint: Confirm that the intended GPT layout and both filesystem mounts were inspected locally.

### Generate and edit the target configuration

Installer console: run `nixos-generate-config --root /mnt`. Inspect
/mnt/etc/nixos/hardware-configuration.nix: it describes detected hardware and
the actual root/boot filesystems. Preserve it and its import; do not replace
its UUIDs with examples or paste it into LearnLab. If mounts are wrong, stop
and correct those before regenerating, preserving any intentional edits.
Interactively edit /mnt/etc/nixos/configuration.nix with `nano` (or `vi`).
Merge these settings inside its existing outer braces, avoiding duplicate
definitions. `lab` is a disposable local account name; choose another if
desired and consistently replace it throughout this walkthrough. The generated
imports must continue to include ./hardware-configuration.nix.

```nix
# Installer console: edit /mnt/etc/nixos/configuration.nix
boot.loader.systemd-boot.enable = true;
boot.loader.efi.canTouchEfiVariables = true;
networking.useDHCP = true;
users.users.lab = {
  isNormalUser = true;
  extraGroups = [ "wheel" ];
};
services.openssh.enable = true;
services.openssh.settings.PermitRootLogin = "no";
services.qemuGuest.enable = true;
environment.systemPackages = with pkgs; [
  curl nftables iproute2 python3 coreutils sudo systemd nano
];
system.stateVersion = "26.05";
```

Classic writable /etc/nixos configuration is intentional. No flakes,
cloud-init, nginx sites, restrictive firewall exercises or systemd exercise
units belong in this base. Keep detected storage/boot settings, and do not
include passwords, private keys, API secrets or password hashes in Nix files
or the Nix store. `system.stateVersion` selects compatibility defaults; leave
it at the original installation release, including during routine upgrades.
Expected: one coherent configuration with both services enabled and the
correct generated hardware import. If syntax or option meaning is unclear,
stop and compare the release manual before installing.

Local checkpoint: Confirm that you reviewed the target configuration and preserved generated hardware settings.

### Keep the installation compatibility version

Installer console: a system installed by this 26.05 walkthrough keeps its
system.stateVersion at 26.05. This is a knowledge question, not a rebuild.

### Install and establish console credentials

Installer console: recheck `findmnt /mnt` and `findmnt /mnt/boot` against the
worksheet. Confirm that you are ready to write the installed OS to these
mounts. Run `nixos-install` interactively. This downloads/builds packages,
writes the OS and installs its bootloader; it is not read-only verification.
Set the requested root password interactively, outside Nix files, shell
arguments, LearnLab answers and notes. After successful installation, run
`nixos-enter --root /mnt -c 'passwd lab'` to set the learner console password
interactively (substitute your chosen account name). Password entry is a
learner action; do not capture it in evidence.
Expected: installer exits successfully and both password operations succeed.
Failed fetch: inspect previous network checks. No space: inspect `df -h /mnt`
and available VM RAM/storage; stop before resizing/retrying. Bootloader error:
inspect UEFI and /mnt/boot. Interrupted installation: inspect mounts, generated
configuration and whether an installer is still running before any retry;
do not format again or claim installation complete.
Proxmox node (management UI): keep the ISO attached as recovery media but set
the verified SCSI disk first in boot order. Installer console: `reboot` only
after installation succeeded. Installed guest: confirm `findmnt /` shows
installed ext4 root rather than live media, and `nixos-version` shows 26.05.
Log in through the Proxmox console as the chosen learner; check `sudo -v`
with the console password. Keep a tested root console recovery route.
If the installer reappears, stop and correct disk boot order; if login fails,
use the root console or deliberately boot the ISO recovery path and inspect
the installed account. Do not remove recovery media until console login works.

Local checkpoint: Confirm successful OS installation and an actual installed-system console login with recovery access.

### Detach the ISO and test the installed disk

Installed guest: after a tested console login, run `poweroff` with appropriate
console privilege and wait for the VM to be stopped in Proxmox.
Proxmox node (management UI): inspect candidate identity again, set CD/DVD to
no media, and enable only the installed SCSI disk in boot order. Retain its
separate EFI variables disk. Start this same candidate and use its console.
Installed guest: log in, inspect `nixos-version`, `findmnt /`, `findmnt /boot`,
`ip -br address`, `ip route`, and the earlier DNS/HTTPS checks. Expected: 26.05,
ext4 root, mounted FAT EFI, DHCP and working HTTPS with no ISO available.
Firmware shell or missing boot entry: stop, inspect SCSI boot order, OVMF and
EFI disk; use retained installation media for deliberate recovery if needed.
Do not continue to access setup until disk-only boot and console recovery pass.

Local checkpoint: Confirm that the installed guest booted and accepted console login with the ISO detached.

## Configure Trusted Lab Access

### Keep the private key on the controller

Installed guest: prerequisite is disk-only 26.05 boot, DHCP/HTTPS, learner
console login and separate root console recovery. On resume inspect current
services and configuration before repeating an activation. Keep the Proxmox
console open throughout access changes. This course records attestations only.
Controller: select an existing suitable SSH key pair or create a dedicated
one interactively with `ssh-keygen -t ed25519`; choose a new owner-only path,
never overwrite an existing key, and enter any passphrase interactively.
Record paths locally. The private key stays on the controller, protected by
local permissions/agent policy. Copy only the single-line public key into the
guest configuration using the trusted console. Never paste either key into
LearnLab answers; never put private keys, passwords or API tokens in Nix/store.
Installed guest: use `sudo nano /etc/nixos/configuration.nix` to merge the
following, replacing the marker with your actual public key locally. Keep
the learner account name consistent with installation; a marker is not a key.

```nix
# Installed guest: merge inside the existing configuration
users.users.lab.openssh.authorizedKeys.keys = [
  "REPLACE_WITH_YOUR_SINGLE_LINE_PUBLIC_KEY"
];
services.openssh.enable = true;
services.openssh.settings = {
  PermitRootLogin = "no";
  PasswordAuthentication = true;
  KbdInteractiveAuthentication = true;
};
services.qemuGuest.enable = true;
security.sudo.enable = true;
security.sudo.extraRules = [ {
  users = [ "lab" ];
  commands = [ { command = "ALL"; options = [ "NOPASSWD" ]; } ];
} ];
environment.systemPackages = with pkgs; [
  curl nftables iproute2 python3 coreutils sudo systemd nano
];
```

Replace earlier duplicate settings rather than defining the same option
twice. Preserve hardware-configuration.nix, boot settings and stateVersion.
The explicit per-account NOPASSWD rule grants full root control to this
disposable lab user. It is intentional for automated labs, unsuitable as a
general production policy, and requires protecting that controller key.
Do not disable passwords yet: first prove key-only login and `sudo -n true`.
Expected: public key only, exactly the intended user in the sudo rule, and
both agent endpoints enabled (Proxmox Options -> QEMU Guest Agent and guest
services.qemuGuest.enable). If the key/account/rule is uncertain, stop before
activation and keep working console access.

Local checkpoint: Confirm the local public-key, lab-only sudo and service configuration review without sharing key material.

### Choose the key material safe for guest configuration

Controller: SSH proves possession of the private key without copying it to
the guest. The matching public key belongs in authorizedKeys; configuration
and the Nix store are not secret storage.

### Test the configuration with a bounded activation

Installed guest (Proxmox console): run the bounded command below from the
console, then inspect its exit status immediately. This changes the running
system; `test` does not make it the boot default and is not a read-only check.

```sh
# Installed guest
sudo timeout --signal=TERM --kill-after=30s 20m nixos-rebuild test
echo $?
sudo visudo -c
sudo -l -U lab
systemctl is-active sshd.service qemu-guest-agent.service
sudo journalctl -b -u sshd.service -u qemu-guest-agent.service --no-pager -n 50
```

Substitute your account for lab. Expected: rebuild exit 0, sudoers syntax OK,
the intended NOPASSWD rule and both services active. Read logs only locally.
Exit 124/137, interruption or any nonzero result: stop. A timeout can leave
partial activation or ongoing build work. Inspect running processes, service
state and console access; do not blindly rerun or assume automatic rollback.
Syntax/unknown option: inspect the local Nix edit. Agent inactive: confirm
Proxmox agent option and guest virtio channel; after a needed virtual hardware
change arrange a deliberate shutdown/start and recheck. SSH inactive: inspect
`systemctl status sshd.service` and its local journal before attempting access.
Proxmox node (management UI): the candidate Summary should obtain network
information through the guest agent. If not, inspect agent settings, channel
and logs even if a DHCP address is otherwise visible. Do not claim agent
operation from an enabled checkbox alone.

Local checkpoint: Confirm successful bounded test activation, checked sudo policy and working guest-agent/service state.

### Verify the SSH server identity before login

Installed guest (trusted Proxmox console): determine its current DHCP address
locally using `ip -br address`. Inspect the effective host-key configuration
with `sudo sshd -T` and fingerprint the configured public host keys using
`sudo ssh-keygen -lf` followed by each observed .pub path. Keep identities
in the owner-only worksheet, never in LearnLab answers or tracked files.
Controller: enter this candidate's inspected address and your key path at
the read prompts. Create a fresh isolated known_hosts file for this candidate:

```sh
# Controller
read -r GUEST_ADDRESS
read -r KEY_PATH
read -r LAB_USER
umask 077
LAB_SSH_DIR=$(mktemp -d)
ssh-keyscan -T 10 -t ed25519,rsa "$GUEST_ADDRESS" > "$LAB_SSH_DIR/candidate-hostkeys"
ssh-keygen -lf "$LAB_SSH_DIR/candidate-hostkeys"
```

Enter the chosen guest username at LAB_USER. ssh-keyscan discovers keys; it
does not establish trust. Compare every discovered key fingerprint/type with
the actual configured keys shown through the trusted console. Empty output,
unexpected key types, missing expected keys or any mismatch means stop before
login. Recheck candidate ownership/address and network path. If your configured
host-key types differ, adapt the scan to that inspected set and compare it
fully. Only after exact local comparison, rename candidate-hostkeys to
known_hosts in this private directory. Keep that directory path in your
private worksheet. This mktemp directory is temporary and may disappear
between sessions. Missing state requires fresh console-verified reenrollment:
inspect ownership/address again, create a new private directory, scan and compare
the full configured key set with the trusted console before enrolling or connecting.
Never recover trust from an unchecked scan or disable strict checking. Never delete global host
entries to silence a DHCP address-reuse warning.
Then make a fresh key-only connection, with your private key still local:

```sh
# Controller
ssh -i "$KEY_PATH" -o IdentitiesOnly=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$LAB_SSH_DIR/known_hosts" -o GlobalKnownHostsFile=/dev/null "$LAB_USER@$GUEST_ADDRESS"
```

A local private-key passphrase prompt is different from a server account
password prompt. Expected: learner shell without server password fallback
or an unverified host prompt. If unavailable, use the console to inspect the
configured public key/account, sshd state and SSH firewall path; stop before
changing authentication restrictions.
Installed guest (new SSH session): run `whoami`, then `sudo -n true` and
immediately `echo $?`. Expected: chosen user and status 0, no password prompt.
Nonzero sudo result: inspect the exact per-user rule with console recovery.
Do not declare success just because an older session remains connected.

Local checkpoint: Confirm console-verified host enrollment, a fresh key-only login and successful noninteractive sudo.

### Disable password SSH only after the access checkpoint

Installed guest (console): after the previous key-login/sudo attestation,
edit the existing services.openssh.settings block to set
PasswordAuthentication = false; and KbdInteractiveAuthentication = false;
while retaining PermitRootLogin = "no". This does not remove console password
recovery. Run the same bounded `nixos-rebuild test` and check exit 0; verify
effective settings with `sudo sshd -T` (passwordauthentication no,
kbdinteractiveauthentication no, permitrootlogin no). Open another fresh
strict key-only controller session using the preceding command; verify
`sudo -n true` again. If any check fails, stop and correct via the open
console; do not close the recovery path or continue to permanent activation.
Once these checks pass, make the tested configuration persistent:

```sh
# Installed guest: permanent activation, not read-only
sudo timeout --signal=TERM --kill-after=30s 20m nixos-rebuild switch
echo $?
```

Expected: exit 0. On timeout/error, inspect state and console as above; do
not claim a permanent generation. After successful switch, deliberately
reboot from the console, then verify console login, fresh trusted key-only
SSH, `sudo -n true`, both services active, agent network reporting, DHCP,
DNS and HTTPS again. Expected: all survive disk-only reboot. A failed boot
means use the console boot menu's prior generation and inspect the Nix edit;
stop before template preparation. Do not change system.stateVersion to fix it.

Local checkpoint: Confirm permanent activation and reboot-tested key-only SSH, sudo, agent and separate console recovery.

### Verify the downstream command contract locally

Installed guest: confirm /etc/os-release identifies NixOS and nixos-version
reports 26.05. The derived downstream union is os.nixos, tool.coreutils,
tool.curl, tool.ip, tool.journalctl, tool.nft, tool.nixos-rebuild, tool.python3,
tool.sudo, tool.systemctl, tool.systemd, tool.systemd-run and tool.timeout.
This bootstrap lesson declares none of those as managed guest capabilities.
Installed packages supply curl -> curl; nftables -> nft; iproute2 -> ip;
python3 -> python3; coreutils -> cat, mkdir, chmod, stat, sha256sum, timeout;
sudo -> sudo/visudo; systemd -> systemctl, journalctl, systemd-run and the
running systemd manager. NixOS supplies nixos-rebuild as a system tool,
not a package named tool.nixos-rebuild. Inspect actual command availability:

```sh
# Installed guest
cat /etc/os-release
nixos-version
command -v cat mkdir chmod stat sha256sum timeout curl nft ip python3 sudo visudo systemctl journalctl systemd-run nixos-rebuild
ps -p 1 -o comm=
systemctl --version
```

Expected: each named command resolves, PID 1 is systemd and OS is NixOS.
Check each command result/output, not only the last command's exit status.
Missing command: inspect environment.systemPackages and the activated
generation; correct through the bounded test/switch sequence and repeat the
affected checks. Do not claim capabilities by merely listing them in TOML.
Keep nginx exercise sites, nftables exercise rules, systemd exercise units
and capstone artifacts absent. Save only local pass/fail for this checkpoint;
the candidate remains a running unsealed VM, not a certified template.
Documentation: https://nixos.org/manual/nixos/stable/ and release options at
https://search.nixos.org/options?channel=26.05 . Package/service behavior and
this walkthrough require live verification; offline tests do not execute them.

Local checkpoint: Confirm locally that OS, every required command and the clean base state were inspected.

## Seal identities and convert the candidate

### Inspect ownership and preserve recovery before sealing

Proxmox node (management UI): begin with the previous section's reboot-tested
NixOS candidate, permanent access configuration, working agent and tools. Reconcile
node, VMID, name, disks/storage and creation task history with the local owner-only
worksheet. VMID alone never proves ownership. Preserve every original working
template, especially one used by another profile. Arrange and verify a separate
backup or powered-off full preservation clone before sealing; explicitly confirm
its creation, new identity and storage cost. Keep that recoverable source until
the new template passes acceptance. Never overwrite an existing resource.

Inspect the candidate's Snapshots tab. Conversion requires a snapshot-free
candidate; do not create a snapshot immediately before conversion. Existing
snapshots are a stop condition: preserve the source and choose a separate
snapshot-free candidate. No automatic snapshot deletion or force conversion.
Read the locally inspected VMID at this node prompt, then inspect each result:

```sh
# Proxmox node: read-only inspection
read -r CANDIDATE_ID
qm status "$CANDIDATE_ID"
qm config "$CANDIDATE_ID"
qm listsnapshot "$CANDIDATE_ID"
```

Expected: intended name/disks, ordinary VM (template absent or 0), no snapshots
except a current-state marker, no active task/lock. Failed lookup means unknown
state. After interruption, inspect task history/config: already a template means
skip resealing and conversion after verifying completed conversion. Partly sealed
or running means inspect exact changes through the console before deciding what
to do. A reboot invalidates known sealed state; repeat the entire inspection phase
before a deliberate reseal. Do not boot an existing template or rerun blindly.

### Inspect NixOS paths, fallback identity and generated SSH units

Installed guest (trusted Proxmox console): retain console recovery. Do not publish
raw identities, fingerprints, addresses or logs. Inspect without writing:

```sh
# Installed guest: read-only inspection
sudo ls -ld /etc/machine-id /var/lib/dbus /var/lib/dbus/machine-id /etc/ssh
sudo stat -c '%F %h %U %a %s %n' /etc/machine-id /var/lib/dbus/machine-id
sudo readlink /etc/machine-id
sudo readlink /var/lib/dbus/machine-id
findmnt -T /etc/machine-id
findmnt -T /var/lib/dbus
findmnt -M /etc/machine-id
findmnt -M /var/lib/dbus/machine-id
cat /proc/cmdline
systemctl --version
nixos-option services.openssh.hostKeys
nixos-option services.openssh.generateHostKeys
nixos-option services.openssh.startWhenNeeded
sudo sshd -T
systemctl cat sshd.service sshd-keygen.service
systemctl show sshd.service -p Wants -p After -p ExecStartPre -p ExecStart
```

Readlink returns nonzero/no output for an ordinary file; findmnt -M does likewise
when the exact path is not a mountpoint. Distinguish these expected outcomes from
permission/I/O failures. A D-Bus identity is absent only after positively inspecting
an accessible parent. Require /etc/machine-id to be a root-owned, single-hard-link
regular file on writable storage, without a bind mount or symlink. D-Bus fallback
must be absent, a verified symlink resolving exactly to /etc/machine-id, or a
separate root-owned single-link regular file on writable storage. A separate
populated D-Bus file can restore the old identity. Stop for read-only storage,
mountpoints, shared hard links, unknown symlinks, overlays or inaccessible paths;
do not unmount/remount, force writes or follow links into the Nix store.

Installed guest: inspect boot.kernelParams and imported Nix configuration for
fixed systemd.machine_id, --machine-id or container_uuid overrides; compare with
the actual kernel command line. Resolve fixed identity configuration before sealing.
Proxmox node: inspect the candidate smbios1 firmware UUID and every NIC MAC locally;
later verify independent clone values. Empty machine-id allows boot initialization,
but differs from a missing file for first-boot condition handling. This sequence
does not depend on ConditionFirstBoot units. [systemd identity source](https://github.com/systemd/systemd/blob/main/man/machine-id.xml).

Installed guest: inspect services.openssh.hostKeys and each private/.pub path using
ls/stat/readlink/findmnt, including parent storage. Require a complete explicit
set matching sshd -T, ordinary unmounted single-link files, writable parents and
no shared/store-backed keys. Do not display private key contents. Verify
generateHostKeys true and startWhenNeeded false. Socket activation/custom units or
an option lookup failure require reconciliation before proceeding.

The inspected release source uses sshd-keygen.service with an ordering/dependency
from sshd.service. Do not assume regeneration lives in ExecStartPre. Read generated
units and referenced store scripts with `sudo less` followed by each observed exact
path; confirm missing configured keys are generated before SSH at boot. Resolve
any mismatch with the active generation; Debian cleanup assumptions do not establish
this behavior. [NixOS 26.05 OpenSSH module](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/services/networking/ssh/sshd.nix).

### Confirm, seal, verify and power off without rebooting

Installed guest (console): explicitly confirm the candidate identity, recovery
source and exact list of per-machine files to clear. Read this whole phase first.
Close all SSH sessions; stop if another operator, rebuild or automatic deployment
could regenerate state during sealing. Then deliberately stop both services:

```sh
# Installed guest: deliberate service mutation
sudo systemctl stop sshd.service sshd-keygen.service
systemctl is-active sshd.service sshd-keygen.service
sudo ss -lntp
```

Require both inactive (nonzero is expected for inactive) and no SSH listener/session.
Remaining SSH or errors mean stop before removing keys. Only for the inspected
ordinary writable machine-id file, run `sudo truncate -s 0 /etc/machine-id` in the
Installed guest and leave the empty file in place. For D-Bus, leave absence alone;
preserve a verified link to /etc/machine-id and confirm it reads empty. Only if it
is a separate validated regular file, run `sudo rm -i -- /var/lib/dbus/machine-id`
and confirm that one deletion. Any other layout is a stop condition.

Installed guest: for each configured host-key pair on the inspected local list,
type `sudo rm -i --` followed by only the exact private and .pub paths, review the
full command and explicitly confirm each removal. This is a manual instruction,
not a placeholder script. No globs, recursive cleanup, authorized_keys deletion
or controller-key deletion. Do not rebuild or run machine-id setup afterward.

Inspect with ls/stat/readlink/findmnt again. Require /etc/machine-id size 0 and
ordinary file, D-Bus fallback absent or the verified empty link, all configured
host-key pairs absent and both services inactive. Partial changes, errors or
reappearing files mean stop and reconcile through the console. After verification,
deliberately power off. Do not reboot or restart SSH: either may regenerate
identities before cloning.

```sh
# Installed guest: deliberate end of sealing
sudo systemctl poweroff
```

Proxmox node (UI): wait for Stopped and successful shutdown task. Timeout or a
closed console does not prove shutdown; inspect task history/status before acting.
Do not force-stop or retry sealing automatically.

### Confirm conversion independently

Proxmox node (UI): re-inspect full ownership, stopped ordinary VM, no active
tasks/locks and no snapshots. If already a template, inspect the completed task
and skip conversion. Select More -> Convert to template and explicitly confirm
the displayed candidate identity. Wait for task success; inspect template: 1 and
the template/disk state. Failure or interruption means unknown state: reconcile
task history/config before doing anything else. Do not remove locks blindly,
delete snapshots, force conversion or boot the template. Retain template and
recovery source. [Proxmox template documentation source](https://github.com/proxmox/pve-docs/blob/master/qm.adoc).

## Accept two full clones

### Create and inspect each clone separately

Proxmox node (UI): verify source node/name/VMID/disks/template flag. Choose two new
IDs and names, A and B; inspect cluster-wide ID/name collisions, including the
template and preservation copy. Failed lookup is unknown state; occupied identities
require inspection or another choice without deletion. Review storage capacity,
target node/storage, then deliberately create A and B separately using Clone ->
Full Clone. Wait for each successful task. Full copies have independent storage
and consume more copy time/space. Inspect new ordinary VM flags, names/IDs/disks,
detached ISO, disk boot order and guest-agent option.

Compare all NIC MACs and smbios1 firmware UUIDs for A, B and the source locally;
require distinct values before starting either clone. Proxmox documents new
MAC/BIOS UUIDs during cloning, but this must be checked on the actual target.
[Proxmox clone documentation](https://github.com/proxmox/pve-docs/blob/master/qm.adoc).
Duplicate identity, unexpected disks or a failed/interrupted clone task means stop
and reconcile resource/config/storage/task history, not repeat creation blindly.
On resume a partially cleaned clone is not a fresh candidate; never recreate or
destroy it by VMID alone. Preserve both templates and the recovery source.

### Prove first-boot access and distinct identities

Proxmox node (UI): deliberately start each inspected clone and open its own trusted
console. Installed guest (each clone): require disk-only login, then inspect:

```sh
# Installed guest: repeat in A and B consoles
cat /etc/os-release
nixos-version
ip -br address
ip route
getent hosts nixos.org
curl --head --fail --max-time 30 https://nixos.org
systemctl is-active sshd.service qemu-guest-agent.service
sudo -n true
cat /etc/machine-id
sudo sshd -T
```

Require NixOS 26.05, DHCP/route/DNS/HTTPS, active services and sudo exit 0. Inspect
each result. Proxmox Summary must receive agent network data on both clones;
connectivity alone does not prove the agent. Failure means console inspection of
guest service, Proxmox option/virtio channel, network and access configuration.

Require nonempty 32-hex-digit machine IDs distinct between A and B (also from the
pre-sealing source if that baseline was retained). Fingerprint every sshd -T host
key using `sudo ssh-keygen -lf` plus each exact .pub path in the Installed guest
console. Require every configured key present and different between A and B for
each key type. Duplicate/empty identity means inspect D-Bus, fixed boot overrides,
firmware and generated keygen units/source sealing. Do not regenerate keys merely
to pass the check. Keep the complete pre-rebuild/reboot baselines only in the
owner-only controller worksheet outside Git, never on the template or in LearnLab.

### Enroll console-authenticated keys in separate isolated files

Controller: repeat separately for each clone, using its console-inspected address:

```sh
# Controller
read -r CLONE_ADDRESS
read -r KEY_PATH
read -r LAB_USER
umask 077
CLONE_SSH_DIR=$(mktemp -d)
ssh-keyscan -T 10 -t ed25519,rsa "$CLONE_ADDRESS" > "$CLONE_SSH_DIR/pending-hostkeys"
ssh-keygen -lf "$CLONE_SSH_DIR/pending-hostkeys"
```

ssh-keyscan alone is not trust. Compare every fingerprint/type to the full configured
set in that clone's trusted console; adapt scanned types to the actual set. Empty,
incomplete or mismatching output means stop before login and recheck ownership,
address and network. Only after exact comparison rename pending-hostkeys to
known_hosts in this directory. Record the distinct directory for each clone and
restore its CLONE_SSH_DIR when switching between clones. Make fresh connections:

```sh
# Controller
ssh -i "$KEY_PATH" -o IdentitiesOnly=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$CLONE_SSH_DIR/known_hosts" -o GlobalKnownHostsFile=/dev/null "$LAB_USER@$CLONE_ADDRESS"
```

Installed guest (fresh SSH session): `whoami`, `sudo -n true`, immediately `echo $?`.
Require intended account and exit 0 without server password fallback. Local key
passphrases are separate. Failures require console diagnosis of account/public key,
firewall and sudo. Keep global known_hosts unchanged when DHCP reuses an address.
Changed address requires console confirmation and a new isolated enrollment
checked against the console and retained baseline. Missing temporary trust state
requires fresh console-verified reenrollment using this entire procedure. Missing
before-reboot baseline means stability is unproven: establish a new baseline and
repeat a deliberate reboot/comparison. Never disable strict checking to recover.

### Rebuild each NixOS clone and verify persistence across reboot

Installed guest (each clone console): preserve hardware configuration/stateVersion
and keep exercise artifacts absent. Inspect command availability and perform a
deliberate bounded clean configuration rebuild:

```sh
# Installed guest: repeat for both clones
command -v cat mkdir chmod stat sha256sum timeout curl nft ip python3 sudo visudo systemctl journalctl systemd-run nixos-rebuild
ps -p 1 -o comm=
systemctl --version
sudo timeout --signal=TERM --kill-after=30s 20m nixos-rebuild test
echo $?
```

Require every command available, PID 1 systemd and rebuild exit 0. Recheck services,
fresh strict key login and sudo. Only after these pass, deliberately run
`sudo timeout --signal=TERM --kill-after=30s 20m nixos-rebuild switch` in the Installed
guest and immediately `echo $?`; require 0. Timeout/124/137, interruption or other
failure means inspect processes/generation/services through console; no blind retry
or assumed rollback. This NixOS rebuild cannot be replaced by a Debian package
reconfiguration recipe. A clean rebuild must not require source-specific identity
or address edits.

Installed guest: explicitly confirm one reboot for A and separately for B, then
run `sudo systemctl reboot` in each console. Keep the template stopped. After each
disk-only boot, repeat network/agent, trusted SSH, sudo, OS/tool checks. Compare
machine ID, every host-key type, firmware UUID and NIC MAC with that clone's
pre-rebuild/reboot baseline. Require each stable and A different from B. Any changed,
empty or duplicate identity fails acceptance; inspect mounts, D-Bus, generated
units and declarative key paths. Do not replace baselines or accept changed keys
to hide failure. Record only pass/fail in LearnLab or shared reports.

Controller: retain templates/recovery source, both learner-owned clones and their
private worksheet for the separate provider/cleanup phase. `learnlab destroy` will
not remove these clones. Cleanup needs its own full ownership inspection, deliberate
confirmation, stop/destroy and absence verification; uncertain state means stop
and reconcile without deletion retries by VMID alone. Exact-digest live acceptance
and final cleanup remain pending; draft status is unchanged.

## Capability mapping and developer derivation

The 2026-09-11 catalog-derived union below is an output contract for the eventual
template, not a capability declaration for this NONE-scope course. Availability
must be checked inside the actual installed guest before any profile claim.

| Capability | Installed source | Actual command or runtime evidence |
| --- | --- | --- |
| `os.nixos` | Installed NixOS 26.05 | `/etc/os-release`, `nixos-version` |
| `tool.coreutils` | `pkgs.coreutils` | `cat`, `mkdir`, `chmod`, `stat`, `sha256sum` |
| `tool.curl` | `pkgs.curl` | `curl` |
| `tool.ip` | `pkgs.iproute2` | `ip` |
| `tool.journalctl` | `pkgs.systemd` | `journalctl` |
| `tool.nft` | `pkgs.nftables` | `nft` |
| `tool.nixos-rebuild` | NixOS system tools | `nixos-rebuild` |
| `tool.python3` | `pkgs.python3` | `python3` |
| `tool.sudo` | `pkgs.sudo`, `security.sudo.enable` | `sudo`, `visudo`, successful `sudo -n true` |
| `tool.systemctl` | `pkgs.systemd` | `systemctl` |
| `tool.systemd` | NixOS system manager, `pkgs.systemd` | PID 1 is `systemd`; `systemctl --version` |
| `tool.systemd-run` | `pkgs.systemd` | `systemd-run` |
| `tool.timeout` | `pkgs.coreutils` | `timeout` |

The QEMU agent is enabled by `services.qemuGuest.enable`; the release module
selects its agent package and connects the service to the virtio port. Adding
`qemu-ga` to PATH is not part of the downstream union. The required end-to-end
evidence is active guest service plus Proxmox guest-agent reporting.

To re-derive requirements without contacting infrastructure, a developer in the
repository can run this on the controller. It unions effective capabilities only
for lessons whose environment contains `os.nixos`.

```sh
# Controller: developer checkout, read-only catalog inspection
PYTHONPATH=src .venv/bin/python - <<'CAPS'
from pathlib import Path
from learnlab.curriculum import CurriculumCatalog
catalog = CurriculumCatalog(Path("src/learnlab/collections"))
required = set()
for summary in catalog.list_courses():
    course = catalog.load_course(summary.path)
    for lesson in course.lessons:
        caps = course.effective_environment(lesson).guest_capabilities
        if "os.nixos" in caps:
            required.update(caps)
print("\n".join(sorted(required)))
CAPS
```

## Primary sources and verification limits

Reviewed on 2026-09-11. These sources substantiate documentation choices, not
execution of this walkthrough. No guest, disk, SSH or Proxmox operation was run
while authoring these sections; exact ISO installation and target-version UI,
package availability, effective service behavior and reboot recovery remain
live-acceptance requirements. Stop at any mismatch with the actual target.

- [Official NixOS downloads](https://nixos.org/download/) exposes the minimal
  Intel/AMD 26.05 image and its checksum link. The moving links observed were
  [minimal x86_64 ISO](https://channels.nixos.org/nixos-26.05/latest-nixos-minimal-x86_64-linux.iso)
  and [matching SHA-256](https://channels.nixos.org/nixos-26.05/latest-nixos-minimal-x86_64-linux.iso.sha256).
  Record the resolved release artifact locally and compare its matching digest;
  do not assume separately retrieved moving links stayed on the same revision.
  [Official release directories](https://releases.nixos.org/nixos/26.05/nixos-26.05.6503.21ea275a7c46)
  demonstrate per-filename SHA-256 publication; this historical example is not a
  pinned ISO choice or a claim to have downloaded/tested that ISO.
- [NixOS 26.05 installation and configuration manual](https://nixos.org/manual/nixos/stable/)
  supports generated hardware configuration, the install/activation distinction,
  persistent account passwords set interactively and installation stateVersion.
  Inspect the release shown by the manual if its stable alias changes.
- [NixOS 26.05 OpenSSH module](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/services/networking/ssh/sshd.nix)
  defines public authorized keys and the SSH settings used here.
- [NixOS 26.05 sudo module](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/security/sudo.nix)
  defines per-user extra rules; inspect the generated rule and run `visudo -c`
  because source validity does not prove the activated guest policy.
- [NixOS 26.05 QEMU agent module](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/virtualisation/qemu-guest-agent.nix)
  defines `services.qemuGuest.enable`, agent package selection and the
  `org.qemu.guest_agent.0` virtio-triggered `qemu-guest-agent.service`.
- [Proxmox-maintained VM documentation source](https://github.com/proxmox/pve-docs/blob/master/qm.adoc)
  documents Q35/OVMF, the 4m EFI variables disk, pre-enrolled keys enabling Secure
  Boot and the guest-agent-backed VM Summary addresses. This upstream source was
  accessible; the rendered [qm reference](https://pve.proxmox.com/pve-docs/qm.1.html),
  VM chapter and administration PDF failed direct retrieval during this review.
  The source is a moving development branch, so confirm labels/options against
  the installed Proxmox version before changing the candidate.

The sealing source refresh also read the current upstream systemd machine-ID
source and NixOS 26.05 OpenSSH module linked above. The rendered systemd identity
page and Proxmox qm reference could not be retrieved; their upstream sources were
accessible. Moving branch sources do not establish the exact installed release's
generated units, path/mount layout, shutdown persistence, snapshot/conversion
behavior or clone/reboot identity results. These remain explicit live blockers.
Offline content tests and local knowledge answers cannot certify the template.
