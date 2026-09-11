# NixOS template course — offline acceptance and live blockers

Status: **draft; offline gate passed; live acceptance not performed**.
Recorded 2026-09-11. The filename follows the design/plan date, 2026-09-10.
Tested content revision: `9f0df3bd15b45e1575e5071668e594f07a373c74`
on `feature/nixos-template-course`. This report is the only subsequent tracked
change in the acceptance-evidence commit. The final whole-branch review finding
about lingering SSH sessions is addressed at the tested content revision; Task 5
Step 5 remains unchecked as instructed. No merge or push is implied.

Course: `proxmox/nixos-template`, seven ordered lessons, effective
`environment.scope: none`, no provider or guest capabilities, and only exact
text evidence/manual confirmations. Knowledge answers and saved progress are
self-attestation, not infrastructure certification. No provider, SSH, Proxmox,
guest, disk, sealing, clone or cleanup operation was executed for this acceptance.

## Exact course digest

```text
215c57675abd952e4d84382b7ba63645dd38ea6972e2bc7bedae26db04a7f91c
```

Computed on the tested revision with this read-only command (exit 0):

```sh
PYTHONPATH=src .venv/bin/python - <<'DIGEST'
from pathlib import Path
from learnlab.course_certification import course_digest
print(course_digest(Path("src/learnlab/collections/proxmox/courses/nixos-template")))
DIGEST
```

The final review fix changed the sealing lesson, so the previous digest is stale.
This digest was recomputed after the fix at `9f0df3b`; recompute it after any
future course change.

## Offline verification

Commands ran in the isolated `template-bootstrap-course` worktree on 2026-09-11
(fresh final-fix gate; pytest completed before 21:09:02 +02:00). Each command
below exited 0:

```text
.venv/bin/python -m pytest -m 'not live' -q
552 passed, 1 deselected in 33.54s

.venv/bin/ruff check .
All checks passed!

.venv/bin/mypy src
Success: no issues found in 17 source files

.venv/bin/learnlab validate proxmox/nixos-template
Validation passed with no findings.

git diff --check
```

The diff check produced no output. The full suite includes the existing single
wheel build/install test: installed curriculum bytes, seven-lesson catalog load,
NONE dependencies, draft status, real no-profile start/save/resume and retained
self-attestation are checked from the installed wheel. Packaging was not rerun
separately. Source CLI regressions also forbid settings/secret/provider/SSH access
and verify saved progress does not grant certification or bypass draft gating.
These tests exercise local software contracts; they do not execute guest commands.

The first Task 5 gate at `8d33390` reported `1 failed, 539 passed, 1 deselected
in 33.55s`: the existing secret-material test rejected the required instructional
field name `token_secret_env` as the substring `token_secret`. Reviewed commits
`fb1e54b` and `6462a1b` corrected that policy and added positive/negative secret
and provider-key cases. The curriculum was unchanged at that point. The earlier
accepted gate at `102c591` reported 550 passed and 1 deselected. This final review
fix changed course content and added two regression cases; the complete gate above
supersedes both earlier results.

Additional read-only `.venv/bin/learnlab validate --format json` exited 0 with
`schema_version: 1`, `ok: true` and exactly these pre-existing warnings, all for
`proxmox/proxmox-admin`:

| Code | Source | Message |
| --- | --- | --- |
| `deprecated-requirements` | `proxmox/courses/proxmox-admin/course.yaml` | requirements is deprecated; use environment.guest_capabilities |
| `missing-os-capability` | `proxmox/courses/proxmox-admin/course.yaml` | A VM environment does not declare an OS guest capability. |
| `manual-confirmation-with-objective-check` | `proxmox/courses/proxmox-admin/lessons/00-api-access/lesson.yaml` | Manual confirmation duplicates an objective check in this step. |

No warning belongs to this bootstrap course; no warning snapshot was changed.

## Lesson and knowledge review

All seven complete lessons were reviewed against the authoritative design's
ordered curriculum, global constraints, destructive checkpoints, verification
and source limitations. The prior task review ledger records Tasks 1–4 complete
and their two deferred minor findings resolved: lost temporary SSH trust requires
fresh console-verified reenrollment; guest poweroff requires positively verified
stopped state, with shutdown-task success only when a management task was initiated.

| Lesson | Offline-reviewed contract; runtime observations remain pending |
| --- | --- |
| `prerequisites-and-safety` | Terminal roles, learner-owned private worksheet, no-profile bootstrap, stop/resume inspection and no automatic infrastructure cleanup. |
| `create-installer-vm` | Official minimal x86_64 ISO/revision/checksum, collision/ownership inspection, Q35/OVMF and Secure Boot choice, separate EFI state disk, new OS disk and DHCP/DNS/HTTPS prerequisites. |
| `install-nixos` | Actual disk/signature/mount inspection; explicit destructive confirmation before interactive GPT/1 GiB EFI/ext4 writes; preserved hardware configuration; installation versus verification distinction; console recovery before ISO detachment and disk-only boot. |
| `configure-lab-access` | Public-key-only configuration, explicit disposable-lab sudo policy, bounded test/switch activation, effective SSH/agent/tool checks, console-authenticated isolated host trust, fresh SSH transport and key/sudo proof before disabling password SSH. |
| `seal-and-convert` | Recoverable source preservation, full ownership/snapshot checks, actual NixOS path/mount/D-Bus/generated-unit inspection, every effective SSH port recorded before service stop, separate listener/established-connection/remaining-sshd-process gates with empty output required, explicit console sealing checkpoint before exact per-file removal, no reboot/restart, verified poweroff and separately confirmed snapshot-free conversion. |
| `test-two-clones` | Separate deliberate full-clone creation, independent disks/firmware/MACs, console-trusted SSH, distinct nonempty machine IDs/host keys, both clean rebuilds, deliberate per-clone reboot and stable identities against private baselines. |
| `configure-provider` | Every current profile field and capability union; preserve profiles/defaults; secret environment-variable name only; read-only health/compatibility limits; independent shutdown/destruction confirmations and positive absence checks for only the two learner-owned clones; retain template/source. |

All seven exact knowledge checks were also exercised through the actual
`TextEvidenceValidator` during Task 5, using each loaded check's `equals` value,
the alternative below, empty input and `unrelated`: **28 decisions passed**.
This supplements the existing parameterized course tests and introductory CLI
positive-case coverage without changing code or tests.

| Check | Accepted | Rejected alternative |
| --- | --- | --- |
| `infrastructure-owner` | `learner` | `learnlab` |
| `media-integrity` | `checksum` | `skip checksum` |
| `install-state-version` | `26.05` | `latest` |
| `key-material` | `public key` | `private key` |
| `sealed-next-action` | `power off` | `reboot` |
| `clone-identity-rule` | `distinct and stable` | `same` |
| `handoff-certification` | `self-attested` | `certified` |

Manual confirmations are separate from knowledge checks. No executable ownership
or mutation guard was added, so a PATH-stub guard matrix is inapplicable. The
content reviews and earlier shell syntax checks cannot establish learner
compliance, safe target identity or guest/Proxmox command semantics.

## Release and source assumptions

The intended target is NixOS **26.05 minimal x86_64**, classic writable
`/etc/nixos/configuration.nix`, Q35/OVMF UEFI, one new disposable OS disk plus
EFI variables storage, an existing LAN bridge with DHCP, and QEMU guest agent.
No ISO was downloaded or selected for acceptance. Exact artifact revision,
checksum, Proxmox version and installed NixOS package/systemd versions are
**not tested or recorded**. Illustrative sizing is not a platform requirement.

The [standalone guide](../NixOS-Template-Guide.md#primary-sources-and-verification-limits)
records the earlier 2026-09-11 primary-source refreshes from Tasks 2–4. Those
refreshes, not a new Task 5 fetch, reported:

- [Official downloads](https://nixos.org/download/) and the
  [NixOS manual](https://nixos.org/manual/nixos/stable/) were accessible. Moving
  ISO/checksum links and the stable manual alias must be resolved to the intended
  release before live use; an example release directory is not a tested ISO.
- Release-specific [OpenSSH](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/services/networking/ssh/sshd.nix),
  [sudo](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/security/sudo.nix)
  and [QEMU agent](https://github.com/NixOS/nixpkgs/blob/nixos-26.05/nixos/modules/virtualisation/qemu-guest-agent.nix)
  module sources were accessible. The dynamic
  [option search](https://search.nixos.org/options?channel=26.05) was unreadable.
  Actual generated units and active option/package behavior remain unobserved.
- The [systemd identity reference](https://manpages.debian.org/trixie/systemd/machine-id.5.en.html)
  was accessible in the final handoff refresh after an earlier failure. Generic
  image semantics do not establish the target NixOS path/mount/D-Bus behavior.
- Rendered [Proxmox qm](https://pve.proxmox.com/pve-docs/qm.1.html) and
  [user-management](https://pve.proxmox.com/pve-docs/pveum.1.html) references
  returned HTTP 403; maintained [VM source](https://github.com/proxmox/pve-docs/blob/master/qm.adoc)
  and [user-management source](https://raw.githubusercontent.com/proxmox/pve-docs/master/pveum.adoc)
  were accessible. Moving development sources do not establish installed-version
  UI/command, conversion, snapshot or storage behavior.

## Required live authorization and protocol — not performed

Before any live resource action, exact scratch candidate/template, preservation
source and two clone identities, expected storage/network effects and explicit
cleanup/retention behavior must be presented privately to the operator and
approved. This includes new disk/EFI/full-copy storage allocations, candidate and
clone network/DHCP/SSH exposure, sealing/conversion changes, and deletion of only
the intended test clones and their attached disks. Implementation approval is
not approval to create, partition, seal, convert, reboot or delete resources.
No such presentation or approval is solicited by this offline report; no real
or invented worksheet values, credentials, raw machine IDs or fingerprints are
included. Inspect ownership again after resume or interruption; VMID alone is
never sufficient.

All checkpoints below remain **pending** until directly observed under that
separate authorization:

1. Resolve a fresh official 26.05 minimal x86_64 ISO and matching checksum;
   record exact non-secret ISO revision, course digest and tested LearnLab
   revision. Verify the intended Proxmox version/help/UI, available storage,
   network, unused full resource identities and a preserved recovery strategy.
2. Traverse all seven lessons from fresh ISO installation. Intentionally fail
   a safe non-destructive check, demonstrate remediation, save progress and
   resume while independently reconciling real resource state. The course
   session must continue to make zero provider/SSH calls.
3. Observe the destructive disk checkpoint, installation, installed console
   recovery, disk-only boot, DHCP/DNS/HTTPS, trusted key-only SSH, noninteractive
   sudo, actual guest-agent reporting and every required command. Verify bounded
   test activation, successful permanent activation and reboot recovery.
4. Inspect actual machine-ID types/mounts/D-Bus fallback, boot identity overrides,
   configured SSH host keys and generated missing-key service dependency. Observe
   every effective SSH port from the actual target configuration before stopping
   SSH. From the console after service stop, require no established connection on
   any recorded port and no remaining sshd process; listener inspection alone is
   insufficient. Observe the remaining console-only sealing, absence/empty-state
   checks, persistence through poweroff, positively verified stopped state and
   snapshot-free template conversion. Unknown ports, permission/output ambiguity,
   unexpected layouts, regeneration, timeout or uncertain task results block
   progression and require reconciliation, not blind retry.
5. Create two separately confirmed full clones. Verify independent copied disks,
   firmware UUIDs and MACs, disk-only boot, guest-agent/network/tool/configuration
   behavior and separately console-authenticated fresh SSH/sudo. Locally compare
   nonempty distinct machine IDs and every configured host-key type. Require both
   clean NixOS rebuilds/permanent activations and one deliberate reboot per clone;
   each clone's own identities must remain stable while the two remain distinct.
6. Add a new named provider profile while preserving existing profiles/defaults.
   Supply credentials privately and observe `learnlab provider test "$PROFILE"`
   plus provider validation of `nginx-nixos/nginx-basics`,
   `nftables-nixos/nftables-basics` and `systemd-nixos/service-authoring`.
   Read-only health and declared compatibility do not prove mutation permissions
   or downstream live certification; downstream execution needs separate scope.
7. Independently inspect, confirm shutdown and confirm destruction for each of
   the two learner-owned test clones only. Verify successful initiated tasks,
   positive stopped state and actual absence from authorized refreshed inventory
   and recorded attached storage. Retain the intended template, recoverable
   source and any original working template. Uncertain cleanup or failed lookup
   requires reconciliation; never infer absence or retry deletion by VMID alone.

Record non-secret pass/fail observations only; raw clone identities and trust
baselines stay in the private worksheet. No registry entry may be added until
every required checkpoint passes for the exact course digest. Keep the closed
certification schema's existing fields; record ISO details in this report rather
than inventing registry fields. Any uncertain observation keeps the course draft.

## Registry and remaining review

Both commands exited 0 with no output on the tested revision:

```text
git diff --exit-code 102c591 -- src/learnlab/collections/certifications.yaml
git diff --exit-code 9f0df3b -- src/learnlab/collections/certifications.yaml
```

The registry is byte-for-byte unchanged from pre-fix `102c591` and tested content
revision `9f0df3b`.
Read-only catalog loading reports `Course maturity: draft`. The implementation
plan checks Tasks 1–4 and Task 5 Steps 1–3 only. Live Step 4 and Task 5 Step 5
remain unchecked; their completion is not claimed here.
