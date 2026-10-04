# Debian 13 template course — offline evidence and live blockers

**Status:** Draft. Offline software checks passed for course content revision
`51a6525f04810e229aee3050cb957ea442c2067c`; final whole-branch review and
exact-digest live acceptance are pending. Recorded 2026-10-04 in the isolated
`codex/learnlab-roadmap` worktree. The filename reflects the plan date.

Course: `proxmox/debian13-template`. The catalog loads seven ordered lessons,
each with effective `environment.scope: none`. LearnLab displays instructions
and records local, self-attested progress. It does not perform the Proxmox,
guest, disk, SSH, sealing, clone or cleanup operations taught here. Passing
knowledge checks or read-only profile checks does not certify a template.

## Exact course digest

```text
8c815d9f0c3df55d0089f2a34c69d18c5cc89c467ed61fc99f14899dda2ce1af
```

Recomputed on 2026-10-04 from the final course directory at revision `51a6525`
using `course_digest(Path("src/learnlab/collections/proxmox/courses/debian13-template"))`.
The course files have not changed since that revision; report and plan edits do
not change this digest. Recompute it after any future course-content edit.

## Offline verification and review evidence

The [Task 4 report](../../.superpowers/sdd/2026-09-10-debian13-template-course/task-4-report.md)
records these current-content results at `51a6525`, before this prose-only
report: full non-live pytest **666 passed, 1 live test deselected**; the existing
wheel build/install test **2 passed**; focused Debian/CLI selection **8 passed**;
and course validation `ok: true` with no findings. The full suite includes the
wheel check. No course, code or test files changed after those checks, so this
report did not rebuild or rerun that suite. Tasks 1–4 have separate spec and
quality review passes in their SDD review files; final whole-branch review has
not happened.

Task 5 read-only checks on 2026-10-04:

| Check | Result |
| --- | --- |
| `PYTHONPATH=src .venv/bin/ruff check --no-cache .` | Pass, no findings |
| `MYPY_CACHE_DIR=/tmp/learnlab-debian13-task5-mypy PYTHONPATH=src .venv/bin/mypy src` | Pass, no issues in 17 source files |
| `PYTHONPATH=src .venv/bin/learnlab validate proxmox/debian13-template --format json` | `ok: true`, no findings |
| `PYTHONPATH=src .venv/bin/learnlab validate --format json` | `ok: true`; only the three existing `proxmox/proxmox-admin` warnings below |
| `CurriculumCatalog(...).load_course` and `list_courses` | Seven expected lesson IDs; maturity `draft` |
| `git diff --check`; registry diff against `HEAD` | No whitespace findings; no registry change |

The first mypy invocation failed before analysis because its inherited cache
database was unwritable (`OperationalError: unable to open database file`).
The fresh run with a `/tmp` cache passed. No code change was needed.

The three catalog-wide warnings belong exclusively to the pre-existing
`proxmox/proxmox-admin` course: `deprecated-requirements`,
`missing-os-capability`, and `manual-confirmation-with-objective-check`. No
warning snapshot was edited to conceal a Debian finding.

Task-level reviews covered the seven-lesson order and scope, safe ownership
checks, official ISO/checksum selection, installer disk confirmation, console
recovery, key and sudo enrollment, SSH boot activation and host-key regeneration,
D-Bus/machine-ID disposition, snapshot-free conversion, independent full-clone
identity checks, read-only profile handoff, and cleanup limited to two verified
test clones. The course tests exercise real `TextEvidenceValidator` decisions:
accepted `checksum`, `13`, `public key`, and `no` concepts pass while their
negative alternatives (`skip checksum`, `12`, `private key`, and `yes`) fail.
The introductory and handoff checks also remain self-attested. Editorial and
software checks cannot establish that the learner executes commands correctly
or that the target Proxmox and Debian versions behave as described.

## Target assumptions and pending live protocol

The intended guest is Debian **13 (trixie) amd64** from an official netinst
ISO, on Proxmox Q35/OVMF UEFI with a disposable VirtIO SCSI OS disk, VirtIO
networking on an existing DHCP LAN bridge, and QEMU guest agent. Secure Boot
compatibility is a deliberate choice to verify. The guide's resource sizes are
illustrative. No ISO was selected or downloaded for this report; its exact 13.x
revision, checksum, installed Debian/systemd/OpenSSH versions, and actual
Proxmox version are unrecorded. The Proxmox `qm` documentation endpoint was
unavailable during authoring, so target-version commands and UI behavior also
need live verification.

No separately authorized live resource run occurred for this digest. Before
one, the operator must privately identify the scratch candidate, retained
source, intended template, two test clones, node, storage and bridge; inspect
unused identities and available resources; review new disk/full-clone storage
allocations, network/DHCP/SSH exposure, and exact cleanup versus retention.
Those private values, credentials, raw machine IDs and host fingerprints do not
belong in this report. The registry remains untouched.

All current-digest acceptance checkpoints remain **pending**:

1. Verify the exact official Debian 13 amd64 netinst artifact and checksum,
   installed Proxmox version, storage/network capacity, identity ownership and
   a recoverable source. Record only non-secret version and pass/fail facts.
2. Traverse all seven lessons from a fresh ISO installation; deliberately fail
   and remediate a safe, non-destructive check; save and resume after reconciling
   real resource state. Confirm the LearnLab session makes zero provider/SSH
   calls.
3. Observe the disk-write confirmation, Debian installer choices, disk-only
   boot, OS/version and package sources, guest agent, required tools, trusted
   key-only SSH, checked lab sudo, and console recovery.
4. Inspect SSH service/socket ordering, host-key generation, DHCP state,
   `/etc/machine-id` and D-Bus behavior on the actual guest. Observe identity
   sealing from the console, no SSH access remaining, verified poweroff,
   snapshot-free conversion and retained source; stop on any uncertainty.
5. Create two separately confirmed **full** clones. Verify independent copied
   disks, firmware/MAC and guest identities, agent/network/SSH/sudo/tool state,
   installed configuration, and distinct nonempty machine IDs and host keys.
   Reboot each once and verify that each clone's own identities remain stable.
6. Add a named profile without replacing existing profiles/defaults. Perform
   read-only provider health and compatibility validation for the matching
   Debian nginx, nftables and systemd courses. These do not prove mutation
   permission or downstream live certification.
7. Independently inspect, confirm shutdown and confirm destruction of only the
   two learner-owned test clones; verify actual absence and attached-storage
   disposition. Retain the intended template, recoverable source and any
   original working template. An uncertain lookup or task result requires
   reconciliation, never a blind retry by VMID.

Every checkpoint must pass for this exact digest before a certification record
can be considered. Any uncertain result keeps the course draft. The final
whole-branch review, its possible fixes and covering checks also remain
pending. No merge, push or live acceptance is implied by this report.
