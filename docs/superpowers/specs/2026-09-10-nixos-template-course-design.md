# NixOS Template Bootstrap Course Design

**Status:** Planned for a later implementation session; no course implementation or live acceptance has started.
**Course:** `proxmox/nixos-template`
**Plan:** [`2026-09-10-nixos-template-course.md`](../plans/2026-09-10-nixos-template-course.md)
**Starting point:** merged pending-course work at `287d350`; always verify current main and reuse later compatible changes.

## Purpose and outcome

Teach a learner to create a reusable NixOS 26.05 Proxmox template from the official minimal x86_64 ISO, understand the decisions, test two clones, and configure a named LearnLab provider. The deliverable is the course plus a standalone operator guide, not a template distributed in Git. The user requested ISO-based learning and the detailed checkpoint/troubleshooting style of the working NixOS guide.

The primary behavioral reference is the user-confirmed corrected guide in **Plan NixOS Learning Lab**, conversation `6a9131c3-5f1c-83ed-a618-b761b8715dfe`: Lesson 00 (installation), Lesson 00B (template preparation), and corrected 00B.9a (generalization and two-clone acceptance). The user reported that the final acceptance test passed. That is historical evidence, not certification of newly authored YAML. This spec reproduces the necessary decisions so a later worker does not depend on access to the conversation. Do not copy its personal VM IDs, addresses, keys, blanket host-key deletion, or original snapshot mistake.

## Architecture and bootstrap boundary

This is a guided **no-environment course** using the existing `EnvironmentScope.NONE`, manual-confirmation and exact text-evidence validators. Start with `learnlab start proxmox/nixos-template --include-drafts` on the controller before a provider profile or template exists. Progress/resume are local. The learner operates the Proxmox GUI/node shell and target VM console explicitly; label every command block `Controller`, `Proxmox node`, `Installer console` or `Installed guest`.

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

Initial target: amd64, Proxmox Q35/OVMF UEFI, one disposable virtual disk, VirtIO SCSI/NIC, ordinary existing LAN bridge with DHCP, and QEMU agent enabled in Proxmox. Explain firmware/Secure Boot choice before booting the unsigned installer. The old guide's 2 vCPU/2 GiB/20 GiB values are illustrative sizing, not required platform defaults; use enough space/RAM for package downloads and builds. No nested virtualization, SDN construction, VLAN redesign, production hardening, encryption, or cloud-init in this course.

Maintain a local owner-only worksheet with node/storage/bridge, candidate VM identity, two clone identities, disk identity, chosen template name and profile name. Never paste it into LearnLab answers or commit it. Check occupied IDs/names before creation; if a name/ID exists, inspect or select another rather than delete or overwrite it. Inspection precedes every destructive action, including after resume.

## Ordered curriculum

| Lesson directory / ID | Required outcome |
|---|---|
| `00-prerequisites-and-safety` | Explain the bootstrap boundary, terminal roles, resource ownership and safe stop/resume. |
| `01-create-installer-vm` | Obtain and verify the minimal x86_64 ISO; create and inspect a new disposable Proxmox VM. |
| `02-install-nixos` | Install NixOS 26.05 from the ISO, explaining disk layout and boot configuration. |
| `03-configure-lab-access` | Configure learner key access, privilege escalation, guest agent and downstream tool contract. |
| `04-seal-and-convert` | Inspect and generalize identities, power off, check snapshots and convert the chosen candidate. |
| `05-test-two-clones` | Boot two full clones, prove distinct identities and stable per-clone identity across a reboot. |
| `06-configure-provider` | Create a new named profile, validate it read-only, retain the template and clean up only test clones. |

The course manifest orders the seven IDs exactly as above without the numeric prefixes. Keep lesson/step/check IDs stable once used; changing existing IDs invalidates progress assumptions. Each lesson begins with required prior state and where to resume safely. Document stop conditions, expected output and at least one concrete troubleshooting branch for each major checkpoint.

## Installation design

Teach the minimal installer from the Proxmox console: identify the assigned virtual disk by size/model, inspect existing signatures and mounts, and get an explicit destructive partitioning confirmation. Teach GPT, a 1 GiB EFI System Partition mounted at `/boot`, and ext4 root. Disk and partition paths are learner-selected inputs, never assume `/dev/sda`. Verify DHCP, route, DNS and HTTPS before installation. Use `nixos-generate-config --root /mnt`, explain both generated files, and preserve the detected hardware configuration. Explicitly configure systemd-boot/UEFI, the learner account, OpenSSH, QEMU guest agent and required packages. `nixos-install` actually installs the system: do not label it a read-only validation command. Establish a console login before detaching the ISO and testing disk-only boot. Keep `system.stateVersion` at the installation release; do not teach changing it as a routine upgrade operation.

## Lab access and capability contract

Use classic writable `/etc/nixos/configuration.nix`, not flakes, immutable deployment or cloud-init. Declare the learner public key and a dedicated disposable-lab sudo policy; never embed passwords, private keys or API secrets in Nix expressions or the Nix store. Demonstrate key login and `sudo -n true` before disabling password SSH. Verify `services.qemuGuest.enable` and `services.openssh.enable`, including effective service state. Install the guest tools in `environment.systemPackages`; map capability names to actual commands rather than assuming equal package names. Include curl, nftables, iproute2, python3, coreutils, sudo and systemd tooling. Require a successful bounded `nixos-rebuild test` and a successful permanent activation before sealing. A timed-out build or activation means inspect state and console access, not blindly rerun.

The bootstrap course itself has **no guest_capabilities**, since it runs without a managed guest. Its output template must provide `os.nixos` plus the actual union of effective capabilities required by shipped matching nginx, nftables and systemd courses. Compute that union from `CurriculumCatalog` at implementation time; document the resulting list and map each `tool.*` to an installed command/package. Do not claim a capability merely by adding it to TOML. Do not preconfigure nginx sites, restrictive firewall rules, systemd exercise units or capstone artifacts in the base template.

## Identity generalization and conversion

Preserve the corrected Lesson 00B.9a sequence from the source session: inspect `/etc/machine-id`, its mount/symlink status, the D-Bus identity path, `services.openssh.hostKeys`, and `sshd.service` before changing identity. Work from the VM console; stop SSH before removing host keys, clear only validated per-machine state, then power off without restarting SSH or rebooting. The default NixOS service should create absent host keys; verify its actual generated unit rather than importing Debian cleanup assumptions. Inspect boot-time identity overrides and confirm clones receive distinct firmware UUIDs/MACs. Never run generic cloud-image cleanup recursively over `/etc`. Check snapshots before conversion; do not create a new snapshot immediately before `qm template`.

Keep a recoverable source until the new candidate passes acceptance. A snapshot blocker is diagnosed explicitly; never automatically delete snapshots to force conversion. If backup/clone preservation is desired, explain its separate storage cost and ownership. Sealing is a phase boundary, not an idempotent command to rerun on any machine: after interruption, inspect whether the candidate is running, sealed or already a template. Rebooting a sealed candidate invalidates its sealed state and requires inspection before repeating that phase.

## Two-clone acceptance and cleanup

Create two **full** clones of the selected template with new independently verified identities. On each, verify disk-only boot, DHCP, guest-agent operation, trusted SSH key login, `sudo -n true`, expected OS and required commands. Verify machine IDs are nonempty and distinct, SSH host public keys/fingerprints are distinct, and Proxmox-generated MAC/firmware identities are not shared. Reboot each clone once and verify that its own machine ID and host keys remain stable. Compare locally; record only pass/fail in public reports.

Use an isolated known_hosts file and verify fingerprints through the Proxmox console/trusted management path before SSH. `ssh-keyscan` alone is not trust; do not delete global known_hosts entries merely because DHCP reused an address. For NixOS, verify a clean rebuild on both clones; for Debian, verify package/service configuration and the missing-key regeneration dependency. Preserve the candidate template and any original working template.

These clones are learner-owned, not in LearnLab's environment database. The course must **not** tell learners that `learnlab destroy` will remove them. Teach explicit Proxmox stop/destroy with the local worksheet, full identity verification, separate confirmation and absence verification. If cleanup is uncertain, stop, retain the worksheet and reconcile state; do not retry deletion by VMID alone. Future downstream-course acceptance uses LearnLab-managed clones and its normal destroy flow separately.

## Provider handoff

Add a new profile in the user's config without overwriting existing profiles/defaults. Explain every current `ProxmoxProfile` field using the README schema: template identity, connection, placement, learner SSH key, verified `template_capabilities`, TLS verification and secret environment-variable name. Tokens are entered outside LearnLab evidence/history. A profile is the connection/template configuration, not merely a template name. API-account setup uses existing operator guidance and read-only permission diagnosis; do not broaden privileges silently or require the VM-scoped proxmox-admin course as a bootstrap prerequisite.

Run `learnlab provider test "$PROFILE"` and `learnlab validate` for the three OS-matching downstream course paths with `--provider "$PROFILE"`. These checks are explicitly read-only but require a chosen profile. They do not prove clone permissions or certify a template/course. Downstream lesson execution needs its own authorization and is outside this task's default offline work.

## Files and integration impact

- `src/learnlab/collections/proxmox/courses/nixos-template/course.yaml` and seven `lessons/*/lesson.yaml` files: packaged curriculum.
- `docs/NixOS-Template-Guide.md`: complete standalone operator walkthrough, including commands, expected output and troubleshooting; the course must remain usable without opening this guide.
- `tests/test_nixos_template_course.py`: schema/order, boundaries, knowledge answers, source safety and capability-output contract.
- `tests/test_cli.py`: actual no-profile start/resume isolation for this packaged course.
- `tests/test_shipped_course_metadata.py`: correct its current VM-only assumption so NONE courses require empty capabilities while VM courses keep nonempty capabilities.
- `tests/test_packaging.py`: extend the existing installed-wheel check to this course without creating another wheel build per test.
- `docs/course-validation/2026-09-10-nixos-template.md`: offline evidence and separate live protocol with exact final digest, no personal data.
- `README.md`: link the guide and explain no-profile draft start.

The two bootstrap tasks may be implemented in either order. They share metadata/CLI/packaging/README test files; the later session must preserve the earlier course's additions. The existing proxmox collection manifest needs no new course list. No changes to existing six course content/digests are intended.

## Verification and certification

Offline: exercise actual catalog loading and validation, test positive/negative knowledge answers, no-profile start and saved progress without provider/SSH access, and installed-wheel inclusion. Safety checks inspect instructions without executing VM/disk commands; structural checks do not prove shell or guest correctness. Where a guard script is introduced, test its decisions with isolated stubs for wrong resource, failed lookup and retry; never test disk formatting against a real device.

Live: separate explicit operator approval identifies resources and cleanup. Traverse all seven lessons from a fresh ISO installation; intentionally fail a non-destructive check; save/resume; perform the two-clone and per-clone reboot tests; retain the template; reconcile cleanup of only the test clones. Record exact ISO revision, course digest, LearnLab revision and non-secret pass/fail observations in the acceptance report. The registry's closed schema permits only its existing fields; put no new ISO field there. Leave registry untouched and course draft until every required live checkpoint passes.

## Sources and freshness

- [NixOS 26.05 manual](https://nixos.org/manual/nixos/stable/): installer and declarative system workflow; version 26.05 was observed during planning.
- [NixOS options](https://search.nixos.org/options): check `services.openssh.hostKeys`, `services.qemuGuest.enable` and relevant package/service options against the target release.
- [Systemd machine identity](https://manpages.debian.org/trixie/systemd/machine-id.5.en.html): generic-image semantics; confirm the target NixOS systemd behavior too.
- [Proxmox qm reference](https://pve.proxmox.com/pve-docs/qm.1.html): recheck target-version conversion/clone/snapshot and guest-agent commands during implementation. The documentation endpoint returned HTTP 403 during planning; no successful fetch is claimed. The earlier session's snapshot rejection is historical evidence to preserve as a test case, not a substitute for current documentation.

Do not copy historical shell prototypes unchanged. Before publication, verify release-specific commands and boot/sealing behavior against these primary sources and the target guest; if unavailable, record a precise live blocker and keep draft status.
