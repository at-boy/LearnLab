# Debian 13 Template Bootstrap Course Design

**Status:** Planned for a later implementation session; no course implementation or live acceptance has started.
**Course:** `proxmox/debian13-template`
**Plan:** [`2026-09-10-debian13-template-course.md`](../plans/2026-09-10-debian13-template-course.md)
**Starting point:** merged pending-course work at `287d350`; always verify current main and reuse later compatible changes.

## Purpose and outcome

Teach a learner to create a reusable Debian 13 (trixie) Proxmox template from the official amd64 netinst ISO, understand the decisions, test two clones, and configure a named LearnLab provider. The deliverable is the course plus a standalone operator guide, not a template distributed in Git. The user requested ISO-based learning and the detailed checkpoint/troubleshooting style of the working NixOS guide.

Use the accepted teaching structure and corrected acceptance criteria from **Plan NixOS Learning Lab**, conversation `6a9131c3-5f1c-83ed-a618-b761b8715dfe`, while implementing Debian-specific installation, account, package, SSH key generation and service behavior. This course must not depend on implementing the NixOS course first. The current working NixOS template is not evidence that the Debian procedure works.

## Architecture and bootstrap boundary

This is a guided **no-environment course** using the existing `EnvironmentScope.NONE`, manual-confirmation and exact text-evidence validators. Start with `learnlab start proxmox/debian13-template --include-drafts` on the controller before a provider profile or template exists. Progress/resume are local. The learner operates the Proxmox GUI/node shell and target VM console explicitly; label every command block `Controller`, `Proxmox node`, `Installer console` or `Installed guest`.

A normal VM-scoped course would require the template it creates; that circular dependency is deliberately avoided. Importing a cloud image and automatic image builds are out of scope. The existing NixOS-administration workstream may continue to exclude template creation: this separate bootstrap course owns it. No changes to provisioning semantics, target adoption, SSH enrollment or CLI flags are planned.

Use separate steps for conceptual questions and execution attestations, so the validator does not report redundant mixed manual/objective checks. Ask for short non-secret concepts, never pasted commands, config files, identities, addresses or service logs. Runtime checks are learner-run instructions and visibly self-attested. Offline passing means the curriculum loads and its contracts are tested, not that a guest was exercised.

## Global Constraints

- Maintain curriculum only under `src/learnlab/collections/`.
- Every lesson in this course uses effective `environment.scope: none`; no provider capability, guest capabilities, remote-command or provider-check declarations are allowed.
- LearnLab displays instructions and records self-attested progress; it must not provision, attach, adopt, seal or destroy learner-created resources.
- No personal infrastructure values, private keys, passwords, API secrets, machine IDs or raw host fingerprints enter tracked curriculum, test evidence, SQLite prompts or certification records.
- Learner input variables are selected and verified locally; VMID alone never establishes resource ownership.
- Installation, identity sealing, template conversion and cleanup require deliberate learner checkpoints; never hide them in a verification command.
- Keep the course draft until exact-digest live acceptance passes; knowledge answers and manual confirmations are not infrastructure certification.
- Preserve Python 3.13 and existing dependency bounds; do not add a bootstrap engine or new validator type.
- Implement in an isolated worktree with TDD and review gates; do not push, merge or perform live operations without explicit authorization.

## Learner prerequisites and target

The learner has LearnLab installed on a controller, access to the Proxmox management UI and node console, permission to create new disposable VMs, reachable ISO/package sources, DHCP and controller-to-guest SSH connectivity, and spare disk/RAM. A LearnLab profile and pre-existing template are **not** prerequisites. Advanced users may configure a profile directly; this course is optional onboarding.

Initial target: amd64, Proxmox Q35/OVMF UEFI, one disposable virtual disk, VirtIO SCSI/NIC, ordinary existing LAN bridge with DHCP, and QEMU agent enabled in Proxmox. Explain firmware/Secure Boot choice and verify compatibility with the selected Debian installer before booting it. The old guide's 2 vCPU/2 GiB/20 GiB values are illustrative sizing, not required platform defaults; use enough space/RAM for package downloads and builds. No nested virtualization, SDN construction, VLAN redesign, production hardening, encryption, or cloud-init in this course.

Maintain a local owner-only worksheet with node/storage/bridge, candidate VM identity, two clone identities, disk identity, chosen template name and profile name. Never paste it into LearnLab answers or commit it. Check occupied IDs/names before creation; if a name/ID exists, inspect or select another rather than delete or overwrite it. Inspection precedes every destructive action, including after resume.

## Ordered curriculum

| Lesson directory / ID | Required outcome |
|---|---|
| `00-prerequisites-and-safety` | Explain the bootstrap boundary, terminal roles, resource ownership and safe stop/resume. |
| `01-create-installer-vm` | Obtain and verify the amd64 netinst ISO; create and inspect a new disposable Proxmox VM. |
| `02-install-debian13` | Install Debian 13 (trixie) from the ISO, explaining disk layout and boot configuration. |
| `03-configure-lab-access` | Configure learner key access, privilege escalation, guest agent and downstream tool contract. |
| `04-seal-and-convert` | Inspect and generalize identities, power off, check snapshots and convert the chosen candidate. |
| `05-test-two-clones` | Boot two full clones, prove distinct identities and stable per-clone identity across a reboot. |
| `06-configure-provider` | Create a new named profile, validate it read-only, retain the template and clean up only test clones. |

The course manifest orders the seven IDs exactly as above without the numeric prefixes. Keep lesson/step/check IDs stable once used; changing existing IDs invalidates progress assumptions. Each lesson begins with required prior state and where to resume safely. Document stop conditions, expected output and at least one concrete troubleshooting branch for each major checkpoint.

## Installation design

Teach the text-mode Debian Installer from the Proxmox console using the official Debian 13 amd64 netinst image. Explain language, keyboard, DHCP/hostname, mirror selection and account setup. Use manual partitioning to teach GPT/UEFI, a 1 GiB EFI System Partition and ext4 root on the selected disposable disk; no LVM/encryption complexity in the first edition. Explain a deliberate no-swap baseline for disposable guests and verify adequate RAM; swap is an optional later topic. Require disk size/model/signature review and explicit destructive confirmation before writing partitions. Select SSH server and standard system utilities, no desktop. Explain the installer root/account choice and ensure an administrator can use the console even if sudo needs installing. Verify `/etc/os-release` reports `ID=debian` and major `VERSION_ID=13`, GRUB EFI boot and disk-only boot after ISO removal. Never substitute a moving `stable` image or teach the controller installation as the target guest.

## Lab access and capability contract

From the guest console install/verify openssh-server, qemu-guest-agent, sudo, curl, nftables, iproute2, python3, coreutils and the account-management tools. Keep nftables inactive with no default-deny rules in the base image; firewall configuration belongs to the downstream course. Confirm online trixie package sources so apt does not prompt for installation media. Establish a learner key and a dedicated disposable-lab sudoers fragment, validate it with `visudo -cf`, then prove new key login and `sudo -n true` before changing SSH authentication. Use absolute privileged paths where Debian places tools under `/usr/sbin`. Check the effective SSH settings and active guest agent; do not treat a static systemd unit's inability to be enabled as a failed installation. Account creation must distinguish an absent account from NSS failure or timeout. Do not set passwords or place secret values in tracked scripts.

The bootstrap course itself has **no guest_capabilities**, since it runs without a managed guest. Its output template must provide `os.debian.13` plus the actual union of effective capabilities required by shipped matching nginx, nftables and systemd courses. Compute that union from `CurriculumCatalog` at implementation time; document the resulting list and map each `tool.*` to an installed command/package. Do not claim a capability merely by adding it to TOML. Do not preconfigure nginx sites, restrictive firewall rules, systemd exercise units or capstone artifacts in the base template.

## Identity generalization and conversion

Do not assume Debian's ssh.service recreates removed host keys. Provide a small root-owned systemd oneshot that runs `/usr/bin/ssh-keygen -A` before `ssh.service`, with a bounded timeout, `RemainAfterExit=yes`, no `ConditionFirstBoot=yes`, and no deletion of existing keys. Wire it with an explicit dependency/drop-in, review with `systemd-analyze verify`, and demonstrate that rerunning it preserves existing host keys. Inspect any SSH socket activation so it cannot bypass that ordering. From the console stop SSH service/socket as applicable, clear only validated host-key files and generalized machine identity, then power off without restarting or rebooting. Inspect `/var/lib/dbus/machine-id`: a stale regular file must not reseed every clone; handle a symlink distinctly. Empty `/etc/machine-id` does not imply systemd ConditionFirstBoot, which is why the key unit must not use that condition. Inspect the actual DHCP client and handle only its known per-machine lease/identity state; verify uniqueness on both clones rather than copying a NixOS cleanup recipe.

Keep a recoverable source until the new candidate passes acceptance. A snapshot blocker is diagnosed explicitly; never automatically delete snapshots to force conversion. If backup/clone preservation is desired, explain its separate storage cost and ownership. Sealing is a phase boundary, not an idempotent command to rerun on any machine: after interruption, inspect whether the candidate is running, sealed or already a template. Rebooting a sealed candidate invalidates its sealed state and requires inspection before repeating that phase.

## Two-clone acceptance and cleanup

Create two **full** clones of the selected template with new independently verified identities. On each, verify disk-only boot, DHCP, guest-agent operation, trusted SSH key login, `sudo -n true`, expected OS and required commands. Verify machine IDs are nonempty and distinct, SSH host public keys/fingerprints are distinct, and Proxmox-generated MAC/firmware identities are not shared. Reboot each clone once and verify that its own machine ID and host keys remain stable. Compare locally; record only pass/fail in public reports.

Use an isolated known_hosts file and verify fingerprints through the Proxmox console/trusted management path before SSH. `ssh-keyscan` alone is not trust; do not delete global known_hosts entries merely because DHCP reused an address. For NixOS, verify a clean rebuild on both clones; for Debian, verify package/service configuration and the missing-key regeneration dependency. Preserve the candidate template and any original working template.

These clones are learner-owned, not in LearnLab's environment database. The course must **not** tell learners that `learnlab destroy` will remove them. Teach explicit Proxmox stop/destroy with the local worksheet, full identity verification, separate confirmation and absence verification. If cleanup is uncertain, stop, retain the worksheet and reconcile state; do not retry deletion by VMID alone. Future downstream-course acceptance uses LearnLab-managed clones and its normal destroy flow separately.

## Provider handoff

Add a new profile in the user's config without overwriting existing profiles/defaults. Explain every current `ProxmoxProfile` field using the README schema: template identity, connection, placement, learner SSH key, verified `template_capabilities`, TLS verification and secret environment-variable name. Tokens are entered outside LearnLab evidence/history. A profile is the connection/template configuration, not merely a template name. API-account setup uses existing operator guidance and read-only permission diagnosis; do not broaden privileges silently or require the VM-scoped proxmox-admin course as a bootstrap prerequisite.

Run `learnlab provider test "$PROFILE"` and `learnlab validate` for the three OS-matching downstream course paths with `--provider "$PROFILE"`. These checks are explicitly read-only but require a chosen profile. They do not prove clone permissions or certify a template/course. Downstream lesson execution needs its own authorization and is outside this task's default offline work.

## Files and integration impact

- `src/learnlab/collections/proxmox/courses/debian13-template/course.yaml` and seven `lessons/*/lesson.yaml` files: packaged curriculum.
- `docs/Debian13-Template-Guide.md`: complete standalone operator walkthrough, including commands, expected output and troubleshooting; the course must remain usable without opening this guide.
- `tests/test_debian13_template_course.py`: schema/order, boundaries, knowledge answers, source safety and capability-output contract.
- `tests/test_cli.py`: actual no-profile start/resume isolation for this packaged course.
- `tests/test_shipped_course_metadata.py`: correct its current VM-only assumption so NONE courses require empty capabilities while VM courses keep nonempty capabilities.
- `tests/test_packaging.py`: extend the existing installed-wheel check to this course without creating another wheel build per test.
- `docs/course-validation/2026-09-10-debian13-template.md`: offline evidence and separate live protocol with exact final digest, no personal data.
- `README.md`: link the guide and explain no-profile draft start.

The two bootstrap tasks may be implemented in either order. They share metadata/CLI/packaging/README test files; the later session must preserve the earlier course's additions. The existing proxmox collection manifest needs no new course list. No changes to existing six course content/digests are intended.

## Verification and certification

Offline: exercise actual catalog loading and validation, test positive/negative knowledge answers, no-profile start and saved progress without provider/SSH access, and installed-wheel inclusion. Safety checks inspect instructions without executing VM/disk commands; structural checks do not prove shell or guest correctness. Where a guard script is introduced, test its decisions with isolated stubs for wrong resource, failed lookup and retry; never test disk formatting against a real device.

Live: separate explicit operator approval identifies resources and cleanup. Traverse all seven lessons from a fresh ISO installation; intentionally fail a non-destructive check; save/resume; perform the two-clone and per-clone reboot tests; retain the template; reconcile cleanup of only the test clones. Record exact ISO revision, course digest, LearnLab revision and non-secret pass/fail observations in the acceptance report. The registry's closed schema permits only its existing fields; put no new ISO field there. Leave registry untouched and course draft until every required live checkpoint passes.

## Sources and freshness

- [Debian 13 amd64 installation guide](https://www.debian.org/releases/trixie/amd64/): installer workflow and target architecture.
- [Debian trixie installation media](https://www.debian.org/releases/trixie/debian-installer/): select the current signed/checksummed 13.x netinst artifact, recording the exact revision during acceptance.
- [Debian systemd machine-id manual](https://manpages.debian.org/trixie/systemd/machine-id.5.en.html): D-Bus fallback and empty-file versus ConditionFirstBoot behavior.
- [Debian ssh-keygen manual](https://manpages.debian.org/trixie/openssh-client/ssh-keygen.1.en.html): `-A` generates missing host keys without replacing present ones.
- [Proxmox qm reference](https://pve.proxmox.com/pve-docs/qm.1.html): recheck target-version conversion/clone/snapshot and guest-agent commands during implementation. The documentation endpoint returned HTTP 403 during planning; no successful fetch is claimed. The earlier session's snapshot rejection is historical evidence to preserve as a test case, not a substitute for current documentation.

Do not copy historical shell prototypes unchanged. Before publication, verify release-specific commands and boot/sealing behavior against these primary sources and the target guest; if unavailable, record a precise live blocker and keep draft status.
