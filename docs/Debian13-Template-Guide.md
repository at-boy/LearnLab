# Debian 13 template guide — installation, sealing and clone checks

This draft guide covers installation, sealing and two-clone checks. Provider
handoff is a later phase. No live installation has been certified. LearnLab records
self-attested answers; it does not create or inspect these resources. Start on
the **Controller** with `learnlab start proxmox/debian13-template --include-drafts`
without a provider profile. Keep node, VM IDs, names, storage, bridge, disk,
addresses, keys and passwords in an owner-only worksheet outside LearnLab.
After interruption, reconcile the real Proxmox and guest state with that
worksheet before continuing. An ID by itself never establishes ownership.

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
run `sudo -n true` in that authenticated session. A local private-key unlock
is allowed; guest password prompt is a failure. Repeat independently for B.

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
file equality and live bus query. Repeat console-authenticated
strict SSH, `sudo -n true`, agent and tool checks. Shared or changed identity,
lost service or access blocks acceptance. Keep raw IDs, fingerprints and
addresses out of LearnLab, Git and reports; record only local pass/fail.
Retain both test clones for the later provider/cleanup lesson. They are
learner-owned; `learnlab destroy` cannot remove them.
