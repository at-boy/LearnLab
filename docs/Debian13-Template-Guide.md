# Debian 13 template guide — installation and lab access

This draft guide covers the first three hands-on phases of the Debian 13
bootstrap course. Later sealing, clone acceptance and provider handoff are
separate phases. No live installation has been certified. LearnLab records
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
account, distinguish a truly absent local account from an NSS failure or
timeout. Check home ownership, `~/.ssh` mode 700 and `authorized_keys` mode
600. Verify the guest host fingerprint through the Proxmox console/trusted
management route, then use a separate controller known_hosts file for SSH.
`ssh-keyscan` alone does not establish trust. Test a fresh key login while the
console is available. On failure inspect account, permissions, ssh.service,
network and logs; do not disable password authentication yet.

**Installed guest — lab sudo and recovery.** In a root console, interactively
write a dedicated root-owned 0440 `/etc/sudoers.d/` fragment for only the
disposable lab account. Validate with `/usr/sbin/visudo -cf
/etc/sudoers.d/<lab-fragment>` and `/usr/sbin/visudo -c` before closing that
console. From a new controller key login run `sudo -n true`; expect exit zero
without a prompt. A failure requires console repair, ownership and `sudo -l`
inspection. Retain a separate administrator console route. Only after key and
sudo checks may you optionally change password SSH settings; inspect effective
`sshd -T`, reconnect in a second session, then end the first. This lab policy
is unsuitable as a default for production hosts.

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

Do not add nginx sites, firewall exercise state, service units or capstone
artifacts to this base guest. The bootstrap course itself remains environment
scope `none` with no managed guest or provider checks.
