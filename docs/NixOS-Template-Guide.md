# NixOS 26.05 Template Guide

Draft: documentation-reviewed, not live-tested. This standalone guide covers all seven course lessons: safety, installer creation, installation, lab access, sealing/conversion, two-clone acceptance, and provider handoff with bounded cleanup. Do not treat these checkpoints as template certification.

LearnLab runs on the controller with `learnlab start proxmox/nixos-template --include-drafts`, without a provider profile. It displays instructions and saves local self-attestations; the learner operates all infrastructure explicitly. A saved answer never establishes current resource ownership.

Prerequisites: permission to create disposable VMs, trusted Proxmox management UI/console access, enough free storage/RAM, existing LAN bridge with DHCP, reachable official ISO/package sources and controller-to-guest SSH. Keep an owner-only worksheet outside this repository with chosen node/storage/bridge, candidate and eventual clone IDs/names, disk identity, template/profile names and private paths. Never paste secrets, personal infrastructure values or raw identities into LearnLab or shared reports. Inspect occupied IDs/names; select another or investigate collisions without deleting anything.

Terminal labels distinguish Controller, Proxmox node, Installer console and Installed guest. Execute each command individually in the labeled location and inspect its result. Installer editors and password prompts are deliberately interactive. Before any destructive action, reconcile full resource identity and repeat the local checkpoint, including after resume.

## Prerequisites and Safety

### Who operates the infrastructure?

Controller: LearnLab records progress. You operate Proxmox and the guest
explicitly. A saved lesson does not prove that a VM still exists or owns
the same ID. Inspect your local resource worksheet before resuming.

Knowledge checkpoint: Who operates the infrastructure here? Enter learner or learnlab.

### Distinguish controller, node, and guest

The controller is the computer where you run LearnLab and keep local
progress. The Proxmox node is the virtualization host you administer.
The guest is the virtual machine that will become the template. Keep
these roles distinct when a later lesson asks you to perform an action.

Local checkpoint: Confirm that you can identify your controller, Proxmox node, and guest.

### Keep an owner-only resource worksheet

Before later lessons, prepare a private, owner-only worksheet outside
this course. Record the node, guest VM ID and name, storage, network,
installation media, and any other local choices you will need. Do not
paste passwords, API tokens, private keys, or personal infrastructure
values into LearnLab, course files, shell history, or shared notes.

Local checkpoint: Confirm that your local worksheet is private and contains no secrets.

### Start without a provider profile

This draft course has no managed environment. Start it with
`learnlab start proxmox/nixos-template --include-drafts` and do not pass
a provider profile. LearnLab presents guidance and records your answers;
it does not contact Proxmox, create a VM, change a guest, or clean up
infrastructure for you.

Local checkpoint: Confirm that this course starts without a provider profile.

### Save progress without assuming infrastructure state

Manual confirmations and saved progress record only what you attested at
the time. They do not inspect current infrastructure or prove that a VM,
VM ID, node, or guest state is unchanged. To stop safely, leave any
manually operated task in a known state, update your private worksheet,
then save and exit. Before resuming, inspect the worksheet and verify the
real node and guest state yourself. LearnLab performs no automatic
cleanup, so you remain responsible for stopping, removing, or preserving
every resource you created.

Local checkpoint: Confirm that you will verify real infrastructure state before resuming.

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
networking.hostId = null;
systemd.services.learnlab-hostid = {
  description = "Generate the persistent LearnLab clone host ID";
  wantedBy = [ "multi-user.target" ];
  after = [ "systemd-machine-id-commit.service" "local-fs.target" ];
  before = [ "multi-user.target" ];
  unitConfig.ConditionPathExists = "!/etc/hostid";
  serviceConfig = {
    Type = "oneshot";
    RemainAfterExit = true;
    User = "root";
    UMask = "0077";
  };
  path = [ pkgs.coreutils pkgs.gnugrep ];
  script = ''
    set -euo pipefail
    export LC_ALL=C
    test "$(uname -m)" = x86_64
    test -d /etc && test ! -L /etc
    test "$(stat -c %u /etc)" = 0
    etc_mode=$(stat -c %a /etc)
    (( (8#$etc_mode & 0022) == 0 ))
    test ! -e /etc/hostid && test ! -L /etc/hostid
    test -f /etc/machine-id && test ! -L /etc/machine-id
    test "$(stat -c %u /etc/machine-id)" = 0
    test "$(stat -c %h /etc/machine-id)" = 1
    test "$(wc -c < /etc/machine-id)" -le 33
    grep -aExq '[0-9a-fA-F]{32}' /etc/machine-id
    machine_id=$(cat /etc/machine-id)
    [[ "$machine_id" =~ ^[0-9a-fA-F]{32}$ ]]
    host_id=''${machine_id:0:8}
    umask 077
    hostid_tmp=$(mktemp /etc/.learnlab-hostid.XXXXXXXX)
    trap 'rm -f -- "$hostid_tmp"' EXIT
    trap 'exit 1' HUP INT TERM
    printf '%b' "\\x''${host_id:6:2}\\x''${host_id:4:2}\\x''${host_id:2:2}\\x''${host_id:0:2}" > "$hostid_tmp"
    test "$(stat -c %s "$hostid_tmp")" = 4
    chown root:root "$hostid_tmp"
    chmod 0444 "$hostid_tmp"
    mv -T --no-clobber -- "$hostid_tmp" /etc/hostid
    test ! -e "$hostid_tmp"
  '';
};
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

This course uses ext4 on x86_64. The persistent LearnLab oneshot waits for
local filesystems and machine-ID commit ordering, validates exactly 32 hex
characters (with at most the normal trailing newline), and derives the
textual host ID from the first eight machine-id characters. It writes four
bytes in native little-endian order, matching NixOS 26.05 on this architecture.
Keep networking.hostId null/unset: a static value makes store-backed identity
shared by clones. This unit is not a substitute for a separately reviewed
ZFS early-boot hostId design; do not adapt it to ZFS or another architecture.
Copy the two single quotes before each shell ${...} exactly: they escape
interpolation in a Nix indented string. They are removed by Nix, not Bash.
The root-controlled same-directory temporary file is checked for four bytes,
root ownership is set, mode is 0444, and rename publishes it atomically.
Existing targets (including dangling symlinks) are never overwritten; invalid
input or a write failure exits nonzero and cleans the temporary file without
leaving a partial target. Do not run concurrent identity writers. The unit
runs only while /etc/hostid is absent and does not rotate an existing ID.
A failed/skipped unit is not proof of valid identity: inspect the checks in
the access lesson. Rebuild and verify this configuration there before sealing.

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
Installer console: after installation and both credential operations succeed,
deliberately run `poweroff`. Proxmox node: re-inspect node, name, VMID,
disks and task history against the worksheet; inspect `qm status` followed
by this exact owned VMID, and require `status: stopped`. A closed console,
timeout or failed lookup is not proof; stop on uncertainty. Only once stopped,
Proxmox node (management UI): keep the ISO attached as recovery media and set
the verified SCSI disk first in boot order before ISO/network. Apply the
setting and re-inspect it on the same owned VM. Start that VM through the UI.
Changing boot order while running and then rebooting is insufficient here.
Installed guest: confirm `findmnt /` shows
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
systemctl is-enabled learnlab-hostid.service
systemctl show learnlab-hostid.service -p ActiveState -p SubState -p Result -p ExecMainStatus -p ConditionResult
systemctl cat learnlab-hostid.service
sudo stat -c '%F %h %U %G %a %s %n' /etc/hostid /etc/machine-id
sudo readlink /etc/hostid
findmnt -T /etc/hostid
findmnt -M /etc/hostid
nixos-option networking.hostId
test "$(hostid)" = "$(head -c 8 /etc/machine-id)"
echo $?
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

Require learnlab-hostid.service enabled, Result=success and ExecMainStatus=0.
On its generation boot expect active/exited with ConditionResult=yes. On a
later boot the existing file makes ConditionResult=no and inactive normal;
that skip alone never proves generation succeeded. Require /etc/hostid a
root-owned single-link regular four-byte file, group root, mode 0444, on the
writable ext4 root, with no symlink, mountpoint or persistence overlay.
Readlink/findmnt -M have no output/nonzero for the expected ordinary layout;
permission/I/O errors mean stop. Inspect /etc/machine-id as a root-owned,
single-link ordinary file containing exactly 32 hex characters (normal
newline allowed), and require the comparison exit 0: hostid equals its first
eight characters. Compare locally only; never print identity values into
LearnLab answers or public reports. networking.hostId must evaluate to null.
Inspect the generated unit: absent-hostid condition, machine-ID commit and
local-fs ordering, oneshot before multi-user completion. Missing/failed unit,
mismatched ID, unexpected layout or option lookup failure means stop; retain
console access, inspect the local journal/configuration, correct through the
bounded rebuild checkpoint, and repeat these checks before sealing. Preserve
this unit and repeat all identity checks after permanent switch and reboot.

Local checkpoint: Confirm successful bounded test activation, checked sudo policy and working guest-agent/service state.

### Verify the SSH server identity before login

Installed guest (trusted Proxmox console): determine its current DHCP address
locally using `ip -br address`. `sshd -T` does not reliably print the multi-value
HostKey directives on every supported OpenSSH build. Inspect the evaluated
`services.openssh.hostKeys` option, then read the generated HostKey directives
and fingerprint exactly their public-key partners:

```sh
# Installed guest: trusted console or trusted Proxmox guest-agent channel
nixos-option services.openssh.hostKeys
sudo awk 'tolower($1) == "hostkey" { print $2 }' /etc/ssh/sshd_config
while IFS= read -r host_key; do
  sudo test -s "$host_key"
  sudo test -s "${host_key}.pub"
  sudo ssh-keygen -lf "${host_key}.pub"
done < <(sudo awk 'tolower($1) == "hostkey" { print $2 }' /etc/ssh/sshd_config)
```

Empty option/directive output, disagreement between them, or a missing key file
means stop. The Proxmox guest-agent channel is an acceptable out-of-band
substitute when the trusted console cannot copy text; an SSH session to the
candidate is not, because using it to authenticate its own host key is circular.
Keep identities in the owner-only worksheet, never in LearnLab answers or tracked
files.

If console copy/paste is unavailable, positively identify the candidate VM on its
Proxmox node, enter that VMID locally, and use the already-verified guest-agent
channel to run the same read-only inspection as guest root:

```sh
# Proxmox node: do not infer or reuse a VMID
read -r VMID
qm config "$VMID"
qm guest exec "$VMID" -- /run/current-system/sw/bin/bash -lc '
set -euo pipefail
while read -r keyword host_key remainder; do
  test "${keyword,,}" = hostkey || continue
  printf "configured-host-key: %s\n" "$host_key"
  test -s "$host_key"
  test -s "${host_key}.pub"
  ssh-keygen -lf "${host_key}.pub"
done < /etc/ssh/sshd_config
'
```

Require successful guest-agent execution and the same complete option, directive
and file agreement. This fallback does not authorize other guest commands or make
an SSH session an out-of-band trust source.
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
ssh -F none -i "$KEY_PATH" -o ControlPath=none -o IdentitiesOnly=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$LAB_SSH_DIR/known_hosts" -o GlobalKnownHostsFile=/dev/null "$LAB_USER@$GUEST_ADDRESS"
```

`-F none` excludes ambient controller SSH configuration; every trust and
authentication input used here is explicit. ControlPath=none disables connection
sharing so this checks a new transport and authentication instead of reusing an
existing SSH connection.
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
sudo ls -ld /etc /etc/hostid
sudo stat -c '%F %h %U %G %a %s %n' /etc/hostid
sudo readlink /etc/hostid
findmnt -T /etc/hostid
findmnt -M /etc/hostid
nixos-option networking.hostId
systemctl is-enabled learnlab-hostid.service
systemctl cat learnlab-hostid.service
systemctl show learnlab-hostid.service -p After -p Before -p Result -p ExecMainStatus -p ConditionResult
test "$(hostid)" = "$(head -c 8 /etc/machine-id)"
echo $?
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

Require the access lesson's validated 32-hex machine-id and a root-owned,
single-link regular four-byte /etc/hostid, group root, mode 0444, on writable
ext4 root with no symlink or mountpoint. /etc itself must be a root-owned
ordinary directory without group/other write access. Require comparison exit
0 and networking.hostId null/unset, never a static value. Inspect imports,
environment.etc, activation scripts and custom units for hostid/machine-id
overrides or competing writers. Require none. Check learnlab-hostid enabled,
successful generation (or the later-boot skip plus a valid persistent file),
its absent-file condition and ordering after machine-ID commit/local-fs and
before multi-user completion. Failed lookup, missing hostid, unsafe layout,
invalid identity, wrong ordering or mismatch means stop before sealing.
This is the ext4 recipe, not a reviewed ZFS early-boot hostId design.

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
no shared/store-backed keys. Require root-owned private/public files, inspect
every owner, and stop for unexpected links or identity overrides.
Do not display private key contents. Verify
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
source and exact list of per-machine files to clear, including /etc/hostid.
Read this whole phase first.
Close all SSH sessions; stop if another operator, rebuild or automatic deployment
could regenerate state during sealing. Before stopping SSH, determine and record
every effective SSH port from this target's actual configuration:

```sh
# Installed guest: read-only effective configuration inspection
sudo sshd -T
```

Record every `port <number>` line locally. Require a nonempty list of valid ports
and a successful, unambiguous command. An empty or malformed port list, a
configuration or permission error, or uncertainty about an Include/custom
unit/socket means stop and reconcile through the console. Then deliberately stop
both services:

```sh
# Installed guest: deliberate service mutation
sudo systemctl stop sshd.service sshd-keygen.service
systemctl is-active sshd.service sshd-keygen.service
sudo ss -Hlnpt
# Repeat separately for every recorded port, replacing PORT with its number.
sudo ss -Htnp state established 'sport = :PORT'
sudo pgrep -a -x sshd
```

`ss -Hlnpt` displays listening sockets; listening sockets alone do not prove
sessions ended. NixOS 26.05 configures `sshd.service` with `KillMode=process`, so
stopping it can leave sshd session children alive. Require both services inactive
and no listener on the recorded ports, then inspect established connections on
every effective SSH port and remaining sshd processes independently. The required
state is no output from every
established-connection query and no output from `pgrep`; inactive and no-match
statuses are nonzero as expected. Any matching connection/process, unexpected
output, permission failure, incomplete port coverage or uncertainty about whether
a command failed is a stop condition: keep console access and do not delete keys
or machine identity.

Only for the inspected ordinary writable machine-id file, run
`sudo truncate -s 0 /etc/machine-id` in the Installed guest and leave the empty
file in place. For D-Bus, leave absence alone; preserve a verified link to
/etc/machine-id and confirm it reads empty. Only if it is a separate validated
regular file, run `sudo rm -i -- /var/lib/dbus/machine-id` and confirm that one
deletion. Any other layout is a stop condition.

Installed guest: re-inspect /etc/hostid against the validated root-owned,
single-link four-byte ordinary file and its writable parent. Only then run
`sudo rm -i -- /etc/hostid` and explicitly confirm this single removal.
Unexpected absence, link, mount, owner, size or any error means stop and
reconcile; do not broaden deletion. Do not start/restart learnlab-hostid or
any identity generator, rebuild, restart SSH or reboot after clearing IDs.

Installed guest: for each configured host-key pair on the inspected local list,
type `sudo rm -i --` followed by only the exact private and .pub paths, review the
full command and explicitly confirm each removal. This is a manual instruction,
not a placeholder script. No globs, recursive cleanup, authorized_keys deletion
or controller-key deletion. Do not rebuild or run machine-id setup afterward.

Inspect with ls/stat/readlink/findmnt again. Require /etc/machine-id size 0 and
ordinary file, D-Bus fallback absent or the verified empty link, /etc/hostid is
absent (including no dangling symlink), all configured
host-key pairs absent and both services inactive. Partial changes, errors or
reappearing files mean stop and reconcile through the console. After verification,
deliberately power off. Do not reboot or restart SSH: either may regenerate
identities before cloning.

```sh
# Installed guest: deliberate end of sealing
sudo systemctl poweroff
```

Proxmox node (UI): positively verify Stopped for the inspected candidate. Guest-side
`systemctl poweroff` may not create a Proxmox shutdown task. Require task success
only if an actual management shutdown task was initiated. A timeout or closed
console does not prove shutdown; inspect the current VM state and any initiated
task before acting. Stop on uncertainty; do not convert a running candidate.
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
systemctl is-enabled learnlab-hostid.service
systemctl show learnlab-hostid.service -p Result -p ExecMainStatus -p ConditionResult
sudo stat -c '%F %h %U %G %a %s %n' /etc/hostid
findmnt -T /etc/hostid
findmnt -M /etc/hostid
nixos-option networking.hostId
test "$(hostid)" = "$(head -c 8 /etc/machine-id)"
echo $?
hostid
nixos-option services.openssh.hostKeys
sudo awk 'tolower($1) == "hostkey" { print $2 }' /etc/ssh/sshd_config
while IFS= read -r host_key; do
  sudo test -s "$host_key"
  sudo test -s "${host_key}.pub"
  sudo ssh-keygen -lf "${host_key}.pub"
done < <(sudo awk 'tolower($1) == "hostkey" { print $2 }' /etc/ssh/sshd_config)
```

Require NixOS 26.05, DHCP/route/DNS/HTTPS, active services and sudo exit 0. Inspect
each result. Proxmox Summary must receive agent network data on both clones;
connectivity alone does not prove the agent. Failure means console inspection of
guest service, Proxmox option/virtio channel, network and access configuration.

On each first clone boot require enabled learnlab-hostid.service, successful
execution with Result=success, ExecMainStatus=0 and ConditionResult=yes.
/etc/hostid must be a root-owned single-link regular four-byte file, group
root, mode 0444, on writable ext4 root, without a symlink or mountpoint.
Require networking.hostId null and comparison exit 0: hostid equals the
first eight characters of that clone's machine-id. A and B host IDs must differ;
also compare with the source baseline if retained. Eight-character collisions
are possible: equal values fail acceptance even with distinct machine IDs.
Missing/mismatched hostid means stop and inspect the oneshot, its ordering,
source sealing and fixed identity overrides; do not alter IDs to force a pass.

Require nonempty 32-hex-digit machine IDs distinct between A and B (also from the
pre-sealing source if that baseline was retained). Require the evaluated hostKeys
option and generated HostKey directives to agree, then fingerprint each exact .pub
path in the Installed guest console. Require every configured key present and
different between A and B for each key type. Duplicate/empty identity means inspect
D-Bus, fixed boot overrides, firmware and generated keygen units/source sealing.
Do not regenerate keys merely to pass the check. Keep the complete pre-rebuild/
reboot baselines only in the owner-only controller worksheet outside Git, never on
the template or in LearnLab.

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
ssh -F none -i "$KEY_PATH" -o ControlPath=none -o IdentitiesOnly=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$CLONE_SSH_DIR/known_hosts" -o GlobalKnownHostsFile=/dev/null "$LAB_USER@$CLONE_ADDRESS"
```

ControlPath=none disables connection sharing; retain it on every repeated
acceptance connection so host-key exchange and authentication run again.
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
disk-only boot, repeat network/agent, trusted SSH, sudo, OS/tool checks, including
hostid layout and its equality to the first eight machine-id characters. Existing
hostid should now skip generation via ConditionResult=no; the valid persistent
file and baseline comparison are required. Compare
machine ID, host ID, every host-key type, firmware UUID and NIC MAC with that clone's
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

## Configure a Provider and Reconcile Test Clones

### Add a new named profile without replacing existing configuration

Controller: prerequisite is successful two-clone acceptance, including
each clone's rebuild and stable identities after reboot. On resume,
inspect the private worksheet and actual template/clone state again.
A profile describes connection, placement and template expectations;
a template name alone is not a profile. This course still loads no
settings, profile, secret or SSH dependency. You make the edits yourself.
Open your existing XDG config file in a local editor: normally
~/.config/learnlab/config.toml, or $XDG_CONFIG_HOME/learnlab/config.toml
when XDG_CONFIG_HOME is set. If absent, create its parent directory and
file in your editor. Keep an owner-only backup outside the repository.
Preserve every existing profile and default_provider. Select an unused
profile name and add a separate [providers."CHOSEN_PROFILE"] table;
replace CHOSEN_PROFILE locally. Do not overwrite a same-named table.
Only for a new configuration with no default_provider, add the top-level
default_provider = "CHOSEN_PROFILE" before the provider tables. An
existing default remains unchanged; the commands below select explicitly.
Enter every required field using locally verified worksheet values:

- type = "proxmox": the supported provider type; name comes from the table.
- api_url: quoted HTTPS API origin, including your port if needed, with
  no credentials, API path, query or fragment; use the controller's trusted CA.
- token_id: quoted existing API account/realm and token identity, not its secret.
- token_secret_env: quoted name of your dedicated environment variable,
  never the secret itself. Choose a name not used by another profile.
- template_vmid: positive integer ID, unquoted, of the inspected template.
- template_name: quoted exact current template name; match both name and ID.
- node: quoted actual node holding that template.
- storage: quoted configured target storage for future managed clone disks.
- network: quoted existing bridge/network identifier for those clones.
- ssh_user: quoted dedicated learner account already tested on both clones.
- ssh_identity_file: quoted controller private-key path for that account;
  the file remains local, and only its public key was installed in the guest.
- tls_verify = true: TOML boolean; fix CA/hostname/clock errors rather than
  disabling verification to obtain a passing health check.
- template_capabilities: optional in the schema, but supply the verified
  string array below for the matching downstream courses. Adding a string
  never installs a command or proves that it runs.

```toml
# Controller: field inside the newly selected provider table
template_capabilities = ["os.nixos", "tool.coreutils", "tool.curl", "tool.ip", "tool.journalctl", "tool.nft", "tool.nixos-rebuild", "tool.python3", "tool.sudo", "tool.systemctl", "tool.systemd", "tool.systemd-run", "tool.timeout"]
```

This union comes from the effective nginx-nixos/nginx-basics,
nftables-nixos/nftables-basics and systemd-nixos/service-authoring
requirements. It is backed by the command/rebuild checks on both clones
from prior lessons, not a compatibility claim based on TOML alone.
Inspect the saved file locally for duplicate tables, missing fields and
TOML types. Do not paste the profile or worksheet into an evidence prompt.
Use an existing authorized API account/token, following your operator's
account setup and the Proxmox User Management/API Tokens guidance at
https://pve.proxmox.com/pve-docs/pveum.1.html . If no suitable account
exists, stop for your administrator to provision one with scoped rights.
Do not run the VM-scoped proxmox-admin course as a bootstrap prerequisite.
Diagnose the selected user, token and resource ACLs read-only; separated
token permissions are limited by both user and token grants. Never grant
broad administrator rights merely to turn a failed check green.

Local checkpoint: Confirm locally that the new profile preserves existing profiles/defaults and contains no secret value.

### Supply the secret privately and check compatibility read-only

Controller: perform these commands yourself only after inspecting the new
profile. They are not run by the course session. At the read prompt enter
the chosen profile name, then check it matches your new TOML table locally.

```sh
# Controller
read -r PROFILE
```

Supply the token secret from a secret manager or an interactive Bash read
in this separate controller shell. For example, if the unique name you
chose in token_secret_env is LEARNLAB_TEMPLATE_TOKEN_SECRET:

```bash
# Controller: use the exact variable name chosen in your profile
read -r -s LEARNLAB_TEMPLATE_TOKEN_SECRET
export LEARNLAB_TEMPLATE_TOKEN_SECRET
printf '\n'
```

Enter the secret at the hidden prompt, never as a command argument,
history entry, LearnLab answer, TOML value or Nix expression. Replace the
example variable name consistently if you selected another. Do not print
it or enable shell tracing. Then run individually and inspect each result:

```sh
# Controller
learnlab provider test "$PROFILE"
learnlab validate nginx-nixos/nginx-basics --provider "$PROFILE"
learnlab validate nftables-nixos/nftables-basics --provider "$PROFILE"
learnlab validate systemd-nixos/service-authoring --provider "$PROFILE"
```

Expected: provider test shows PASS for required API/node/template/storage/
network checks, exit status 0; each validate reports no errors and exits 0.
Inspect `echo "$?"` immediately after each command if needed. Draft warnings
do not confer certification. These are read-only health and declared
compatibility checks; they do not prove clone permissions, execute guest
commands or certify this template or any downstream course. Permission to
read resources is not permission to clone, start, modify or delete them.
A missing profile/field/secret means inspect the local table and environment
variable name; never reveal the secret in diagnostic output. TLS failure
means inspect certificate trust, API hostname and clock. API denial means
inspect existing user/token ACL scope with the administrator; do not broaden
privileges silently. Wrong template/node/storage/network means compare full
observed identity with the worksheet. Missing capability means return to
actual guest configuration and two-clone tests, not just adding TOML strings.
Stop on failures and retain resources for diagnosis. Remove the exported
secret from this shell when finished with `unset LEARNLAB_TEMPLATE_TOKEN_SECRET`
(using your selected name). Keep only non-secret pass/fail notes.

Local checkpoint: Confirm that you ran the chosen profile health and three compatibility checks yourself and reviewed their limits.

### Remove only the two learner-owned acceptance clones

Proxmox node: these two test clones are learner-owned and untracked by
LearnLab. Do not use learnlab destroy to remove them: it cannot destroy
untracked clones. Later authorized downstream sessions create separately
managed environments with their own normal destroy flow.
Cleanup permanently deletes each selected clone and its attached disks.
Keep the private worksheet until absence is positively verified. Always
retain the template, the recoverable source and any original working
template. They are outside this cleanup boundary. If acceptance failed,
stop and diagnose before deciding whether these test clones can be removed.
Work on one clone at a time; no loops, ranges or bulk removal. In the
trusted management UI reconcile cluster/node, clone name and ID, creation
history, storage volumes, MAC/firmware identity and the worksheet. Confirm
this is one of the two disposable full clones and not a template/source,
another profile's VM or any replacement that reused an ID. VMID alone is
insufficient. Reinspect after every interruption or failed lookup.
In the shell on the verified owning node, set CLONE_VMID from that observed
clone and inspect the output locally. Do not paste it into LearnLab:

```sh
# Proxmox node: inspect one already reconciled clone
read -r CLONE_VMID
qm config "$CLONE_VMID"
qm status "$CLONE_VMID"
```

Expected: correct name/disks/MAC/firmware identity, no template flag and
a known running/stopped state. Any failed command or ambiguity means stop.
Separately confirm locally that this exact disposable clone may be shut
down. If running, request graceful shutdown in the UI, or individually:

```sh
# Proxmox node: only after the shutdown confirmation
qm shutdown "$CLONE_VMID"
```

Require successful completion of the initiated management shutdown task
and positively verify Stopped in the UI and `qm status "$CLONE_VMID"`.
If already stopped, there is no new shutdown task to require. A timeout,
closed console or failed lookup is not proof of stopped state. Do not
silently escalate to force-stop; inspect console/tasks and reconcile first.
Before deletion, repeat full identity inspection and verify no other work
uses this clone. Make a separate explicit local destruction confirmation
naming that clone and its attached disposable disks. Only then use the
UI Remove confirmation for that clone or execute this single command:

```sh
# Proxmox node: only after the separate destruction confirmation
qm destroy "$CLONE_VMID"
```

Do not add purge, skiplock, force or delete-unreferenced-disk options.
Expected: successful removal task and absence of this clone from a
successfully refreshed authorized cluster VM inventory. Inspect storage
for absence of its recorded attached volumes and confirm the retained
template/source remain present. A failed qm config lookup alone cannot
establish absence: it could mean wrong node, denied access or lost service.
If deletion/task/status/inventory is uncertain, stop, retain the worksheet
and reconcile with the administrator. Never retry deletion by VMID alone.
Only after the first clone is reconciled, repeat these independent checks
and confirmations for the second worksheet clone. Record only pass/fail
and retained-template/cleanup status in shared notes, never raw identities.

Local checkpoint: Confirm locally that only the two inspected test clones are absent and the template and source are retained.

### Keep learner progress separate from live certification

Controller: successful knowledge answers and manual confirmations save
self-attested progress. Even completion of all seven lessons grants no
live certificate. The course remains draft and the certification registry
remains unchanged. A downstream live run needs its own authorization and
exact-digest acceptance, including mutation permissions and cleanup of its
separately managed clones. Do not treat read-only health as that approval.

Knowledge checkpoint: What kind of progress do these manual confirmations record? Enter self-attested.

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

Host-ID correction sources rechecked on 2026-09-14:

- [NixOS 26.05 networking identity option and file generation](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/tasks/network-interfaces.nix)
  defaults networking.hostId to null and recommends taking the first eight
  machine-id characters. Setting it generates a shared store-backed hostid, which
  this clone recipe deliberately avoids.
- [NixOS 26.05 stage-1 hostid encoding](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/system/boot/stage-1.nix)
  reverses the four byte pairs on little-endian targets such as x86_64. The
  course oneshot uses that byte order after machine-ID availability on ext4;
  it is not an initrd/ZFS design. Documentation was rechecked for this correction;
  generated-unit behavior, first-boot creation and reboot stability still require
  separately authorized live acceptance.

The remaining source review dates to 2026-09-11. These sources substantiate documentation choices, not
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

- [NixOS option search](https://search.nixos.org/options?channel=26.05) is the
  release-selectable reference for `services.openssh.hostKeys` and
  `services.qemuGuest.enable`. The dynamic option page was not readable during
  this refresh; use the release-specific modules above and inspect the generated
  guest units before sealing.
- [Systemd machine identity reference](https://manpages.debian.org/trixie/systemd/machine-id.5.en.html)
  was accessible in the final handoff review after an earlier fetch failed.
  It describes generic-image identity semantics; it does not establish the
  target NixOS release's effective path/mount/unit behavior.
- [Proxmox User Management source](https://raw.githubusercontent.com/proxmox/pve-docs/master/pveum.adoc)
  documents API token permission separation and the intersection of user/token
  grants. The rendered [user-management reference](https://pve.proxmox.com/pve-docs/pveum.1.html)
  returned HTTP 403 in this refresh. Use your installed-version operator guidance
  and administrator for account setup; no account or privilege change was tested.
- The [upstream qm source](https://raw.githubusercontent.com/proxmox/pve-docs/master/qm.adoc)
  also documents shutdown/wait and destroy. The handoff requires positive stopped
  state and independent removal verification; it deliberately requires local
  ownership checks and confirmations before these learner-operated mutations.
  Rendered qm retrieval still returned HTTP 403. No exact Proxmox release has
  been live-validated for this walkthrough; check its installed help/UI first.

The sealing source refresh also read the current upstream systemd machine-ID
source and NixOS 26.05 OpenSSH module linked above. Moving branch sources do not
establish the exact installed release's
generated units, path/mount layout, shutdown persistence, snapshot/conversion
behavior or clone/reboot identity results. These remain explicit live blockers.
Offline content tests and local knowledge answers cannot certify the template.
