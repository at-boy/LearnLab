# NixOS 26.05 Template Guide

Draft: documentation-reviewed, not live-tested. This first portion covers installer creation, installation and lab access. The result is an unsealed candidate VM; sealing, conversion and two-clone acceptance are later course tasks. Do not treat these checkpoints as template certification.

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
private worksheet; retain it for later sessions. Never delete global host
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

The base should now have only installation and access configuration. Leave it
unsealed until the separate identity-generalization lesson is available and
completed. Offline content tests and local knowledge answers cannot certify it.
