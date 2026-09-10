# LearnLab Course Authoring Guide

*How to design, write, validate, and ship interactive courses for LearnLab.*

> **Note on formats:** LearnLab curriculum is **YAML**, organized as *collections → courses → lessons → steps → verifications*. This guide documents the real loader schema. Any TOML-style sketches you may have seen elsewhere are superseded by this document.

---

## Table of Contents

1. [How LearnLab courses work](#1-how-learnlab-courses-work)
2. [On-disk layout](#2-on-disk-layout)
3. [IDs, keys, and the strict loader](#3-ids-keys-and-the-strict-loader)
4. [Walkthrough: build a course from scratch](#4-walkthrough-build-a-course-from-scratch)
5. [Verification design guide](#5-verification-design-guide)
6. [Environments, scopes, and capabilities](#6-environments-scopes-and-capabilities)
7. [Security and content rules](#7-security-and-content-rules)
8. [Testing your course](#8-testing-your-course)
9. [Shipping and versioning](#9-shipping-and-versioning)
10. [Troubleshooting](#10-troubleshooting)
11. [Appendix A: schema reference](#appendix-a-schema-reference)
12. [Appendix B: CLI quick reference](#appendix-b-cli-quick-reference)
13. [Appendix C: pre-ship checklist](#appendix-c-pre-ship-checklist)

---

## 1. How LearnLab courses work

### 1.1 The content hierarchy

```text
Collection          "nixos"                 a subject family
 └── Course         "vm-management"         one learnable track, ordered lessons
      └── Lesson    "first-vm"              one session; owns 0..1 environment override
           └── Step "provision-vm"          one teaching beat: instructions + checks
                └── Verification            one ordered, required check
```

* **Lessons are ordered** by the explicit `lessons:` list in `course.yaml` — not by directory names.
* **Verifications are ordered and all required.** A step completes only when every check passes, in the order shown. A lesson completes when its steps complete.
* **Progress is resumable.** `learnlab start` / `learnlab resume` continue at the first incomplete verification; earlier passed checks stay recorded in the local SQLite state.

### 1.2 The four verification types

| Type | What it does | Passes when | Typed fields |
|---|---|---|---|
| `remote-command` | Runs a curriculum-authored command non-interactively over SSH in the learner's environment | exit status is `0` | `command`, `timeout_seconds` (1–300, default 30) |
| `text-evidence` | Compares the learner's bounded answer (≤ 8 KiB) to a configured value | exact `equals`, or `matches` regex | `prompt`, exactly one of `equals` / `matches` |
| `manual-confirmation` | Records a clearly labeled self-attestation | learner confirms | `prompt` |
| `provider-check` | Invokes a named **read-only** provider inspection (never mutates infrastructure) | inspection succeeds | `check` |

All types also accept `id`, `type`, and optional `failure_message`.

**Key mental model:** LearnLab never turns learner text into a shell command. Remote commands come *only* from reviewed curriculum and are passed as one remote argument. Knowledge checks therefore belong in `text-evidence`, not in "type a command and we'll run it" flows.

---

## 2. On-disk layout

The only maintained curriculum tree is `src/learnlab/collections/`. Repository
validation and installed wheels read these same package resources, so authors do
not maintain a second top-level copy.

```text
src/learnlab/collections/
└── nixos/                              # one directory per collection
    ├── collection.yaml                 # {id, title}
    └── courses/
        └── vm-management/              # directory name == course id
            ├── course.yaml             # {id, title, environment, [requirements], lessons}
            └── lessons/
                ├── 00-hypervisor-basics/   # "<NN>-<lesson-id>"
                │   └── lesson.yaml
                ├── 01-first-vm/
                │   └── lesson.yaml
                └── 02-snapshots/
                    └── lesson.yaml
```

Rules the loader enforces:

* The **course path** used by the CLI is `collection/course`, e.g. `learnlab start nixos/vm-management --provider home-proxmox --include-drafts` for this guide's uncertified example.
* `collection.yaml` `id` must equal its directory name; `course.yaml` `id` must equal its directory name; `lesson.yaml` `id` must equal its lesson id.
* Lesson directories must **end with `-<lesson-id>`** (e.g. `01-first-vm` for id `first-vm`), and **exactly one** directory may match each id. Numeric prefixes are only labels for humans; even numeric lesson IDs and directory prefixes never determine ordering. Ordering comes solely from `course.yaml`.

---

## 3. IDs, keys, and the strict loader

### 3.1 ID grammars

| Kind | Pattern | Examples |
|---|---|---|
| Stable ID (collections, courses, lessons, steps, verifications) | `[a-z0-9]+(?:-[a-z0-9]+)*` | `api-access`, `first-vm`, `kvm-device-present` |
| Capability ID (`provider_capability`, `guest_capabilities`) | `[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*` | `proxmox.vm`, `os.debian.13`, `tool.curl` |

No uppercase, no underscores, no leading/trailing hyphens. IDs must be unique within their parent (lessons in a course, steps in a lesson, verifications in a step).

### 3.2 Exact-key discipline

The loader rejects **unknown and missing keys** everywhere. This is deliberate: a typo must fail at load time, not silently become a broken lesson.

| File | Required keys | Optional keys |
|---|---|---|
| `collection.yaml` | `id`, `title` | — |
| `course.yaml` | `id`, `title`, `lessons`, `environment` | legacy `requirements` during migration only |
| `lesson.yaml` | `id`, `title`, `steps` | `environment` |
| step | `id`, `title`, `instructions` **or** `content`, `verifications` | — |
| environment block | `scope` | `provider_capability` and `guest_capabilities` for VM scopes; both forbidden with `none` |

* `instructions` and `content` are mutually exclusive aliases; prefer `instructions` for new content.
* `lessons`, `steps`, `verifications` must be **explicit, non-empty YAML lists** with no duplicates.

---

## 4. Walkthrough: build a course from scratch

We'll build `nixos/vm-management` — *Creating and Managing Virtual Machines in NixOS* — assuming a NixOS learning VM template with libvirt/QEMU and a pre-cached Cirros image at `/var/lib/libvirt/images/cirros.img`.

This nested-virtualization walkthrough is illustrative authoring guidance. It
has not been run as a live course or certified against a compatible template,
so it is explicitly **uncertified**. If added to the catalog as shown, start it
only through the draft opt-in while it is being developed:

```bash
learnlab start nixos/vm-management --provider scratch-profile --include-drafts
```

### 4.1 `src/learnlab/collections/nixos/collection.yaml`

```yaml
id: nixos
title: NixOS
```

### 4.2 `src/learnlab/collections/nixos/courses/vm-management/course.yaml`

```yaml
id: vm-management
title: Creating and Managing Virtual Machines in NixOS
environment:
  scope: course                 # one disposable VM reused for the whole course
  provider_capability: proxmox.vm
  guest_capabilities:
    - os.nixos
    - tool.virsh
    - feature.nested-virtualization
lessons:
  - hypervisor-basics
  - first-vm
  - snapshots
```

* `scope: course` is right here because later lessons operate on the VM created in earlier lessons.
* `provider_capability` selects the supported provider kind. The optional
  `guest_capabilities` list declares what the configured template must already
  contain; it is provider-neutral and may include OS, tool, and feature IDs.

### 4.3 Lesson 1 — `lessons/00-hypervisor-basics/lesson.yaml`

```yaml
id: hypervisor-basics
title: Hypervisor Basics
steps:
  - id: inspect-hypervisor
    title: Inspect the hypervisor
    instructions: >-
      Your disposable learning VM runs NixOS with libvirt and QEMU/KVM
      preinstalled. KVM is the kernel component that turns Linux into a
      hypervisor. Inspect the VM's virtualization support before creating
      anything.
    verifications:
      - id: kvm-device-present
        type: remote-command
        command: test -c /dev/kvm
        failure_message: The learning VM must expose /dev/kvm; nested virtualization is not reaching the VM.
      - id: libvirtd-active
        type: remote-command
        command: systemctl is-active --quiet libvirtd
        failure_message: libvirtd must be active on the learning VM.
      - id: explain-kvm
        type: text-evidence
        prompt: Which Linux kernel component provides hardware-accelerated virtualization?
        matches: '(?i)\bkvm\b|kernel-based virtual machine'
  - id: describe-virt-stack
    title: Describe the virtualization stack
    instructions: >-
      In one or two sentences, describe how QEMU, KVM, and libvirt divide the
      work of running a virtual machine.
    verifications:
      - id: explain-stack
        type: text-evidence
        prompt: What role does libvirt play in the QEMU/KVM stack?
        matches: '(?i)manag|daemon|api|control'
```

Notes:

* Readiness checks (`test -c /dev/kvm`, `systemctl is-active --quiet`) come **first**; knowledge checks come after.
* `systemctl is-active --quiet` and `test` are the ideal `remote-command` shape: silent, fast, exit-status driven.

### 4.4 Lesson 2 — `lessons/01-first-vm/lesson.yaml`

```yaml
id: first-vm
title: Create Your First VM
steps:
  - id: provision-vm
    title: Provision a minimal VM
    instructions: >-
      A small Cirros disk image is pre-cached at
      /var/lib/libvirt/images/cirros.img. Use virt-install to import it as a
      VM named lab-vm with 256 MiB of RAM, one vCPU, and no graphics, then
      confirm it is running with virsh.
    verifications:
      - id: vm-defined
        type: remote-command
        command: virsh domuuid lab-vm
        failure_message: A VM named lab-vm must be defined; use virt-install --import with the cached image.
      - id: vm-running
        type: remote-command
        command: virsh domstate lab-vm | grep -qx running
        failure_message: lab-vm must be running; start it with virsh start lab-vm.
      - id: memory-bounded
        type: remote-command
        command: test "$(virsh dominfo lab-vm | awk '/Max memory/ {print $3}')" -le 524288
        failure_message: Keep lab-vm at 512 MiB of RAM or less so the learning VM stays responsive.
  - id: explain-import
    title: Explain what you used
    instructions: >-
      Review the virt-install manual page section on disk installation options.
    verifications:
      - id: import-flag
        type: text-evidence
        prompt: Which single virt-install flag imports an existing disk image instead of installing an OS?
        equals: --import
```

Notes:

* `grep -qx running` makes the check exact and exit-status based.
* The memory bound protects the shared learning VM from learner over-allocation — a good example of a *policy* verification.
* `equals: --import` shows exact matching; use `equals` only for short, unambiguous tokens.

### 4.5 Lesson 3 — `lessons/02-snapshots/lesson.yaml`

```yaml
id: snapshots
title: Snapshots and Lifecycle
steps:
  - id: snapshot-revert
    title: Snapshot and revert
    instructions: >-
      Create a snapshot of lab-vm named clean, force-stop the VM with virsh
      destroy, then revert to the snapshot and start the VM again.
    verifications:
      - id: snapshot-exists
        type: remote-command
        command: virsh snapshot-list lab-vm --name | grep -qx clean
        timeout_seconds: 60
        failure_message: A snapshot named clean must exist for lab-vm.
      - id: vm-running-again
        type: remote-command
        command: virsh domstate lab-vm | grep -qx running
        timeout_seconds: 60
        failure_message: After reverting, lab-vm must be running again.
  - id: cleanup
    title: Clean up
    instructions: >-
      Stop lab-vm and undefine it. Keep the cached base image; only remove the
      VM definition you created.
    verifications:
      - id: vm-removed
        type: remote-command
        command: test -z "$(virsh list --all --name | grep -x lab-vm)"
        failure_message: lab-vm must be undefined; run virsh destroy lab-vm and virsh undefine lab-vm.
      - id: reviewed-lifecycle
        type: manual-confirmation
        prompt: Confirm that you reviewed the full lifecycle you just exercised (create, run, snapshot, revert, destroy).
```

Notes:

* Snapshot/revert can be slow, so `timeout_seconds: 60` (allowed range 1–300).
* `manual-confirmation` closes the lesson as an honest self-attestation — exactly its intended use.

---

## 5. Verification design guide

### 5.1 `remote-command` — exit status is everything

A `remote-command` passes **only on exit status 0**. Output is not compared. Design commands accordingly:

| ❌ Bad | ✅ Good | Why |
|---|---|---|
| `cat /etc/os-release` | `test -r /etc/os-release` | Output is ignored; assert with `test` |
| `virsh domstate lab-vm` | `virsh domstate lab-vm \| grep -qx running` | Raw output always exits 0 |
| `ping 8.8.8.8` | `ping -c 2 -W 2 8.8.8.8` | Unbounded commands hit the timeout |
| `sudo apt update` | read-only checks, or bounded local asserts | Slow, mutating, prompt-prone |
| `grep error /var/log/x` | `grep -q pattern file` | Quiet flags keep output tiny |

Rules of thumb:

* **Idempotent and re-runnable.** Verifications re-run on resume and retry; passing once must mean passing again.
* **Non-interactive.** Batch-mode SSH means prompts = hangs = timeouts. Never rely on `sudo` password prompts.
* **Small output.** Remote output capture is bounded (8 KiB); keep commands quiet (`--quiet`, `-q`, `test`).
* **Bounded runtime.** Default timeout is 30 s; raise to at most 300 s only for genuinely slow operations (snapshots, builds).
* **Absolute paths.** The remote working directory is the learner's default; never assume a cwd.
* **Read-only preferred.** If a check must mutate, mutate only learner-owned artifacts inside the disposable environment.

### 5.2 `text-evidence` — knowledge checks

* Use `equals` for a single canonical token (`--import`, `virsh`). Exact means exact; keep expected answers short.
* Use `matches` for prose. It is a Python regular expression compiled at load time:
  * Tolerate casing with `(?i)` — the shipped course uses `(?i)interface|boundary`.
  * Tolerate phrasing with alternation and stems: `(?i)separat|audit|permission`.
  * Anchor (`^…$`) when you need precision.
* Make the answer **derivable from the instructions** — the check should confirm reading, not guesswork.
* Answers are bounded to 8 KiB; write prompts that expect one or two sentences.

### 5.3 `manual-confirmation` — self-attestation

* Use for "I reviewed the guidance" moments (security principles, ethics, visual inspection).
* Never use it as a substitute for an objective check that *could* be a `remote-command` or `text-evidence`.
* The platform labels it as self-attestation in recorded provenance; design prompts that read honestly under that label.

### 5.4 `provider-check` — readiness gates

* Named **read-only** provider inspections; they never create, start, stop, reconfigure, or delete infrastructure.
* The shipped Proxmox course uses `vm-running` and `guest-agent-ready`. Place these **before the first `remote-command`** of a course so SSH checks never race provisioning:

```yaml
- id: learning-vm-running
  type: provider-check
  check: vm-running
  failure_message: Wait for the disposable learning VM to report as running.
- id: learning-vm-agent-ready
  type: provider-check
  check: guest-agent-ready
  failure_message: Wait for the disposable learning VM guest agent to respond.
```

* Available check names are defined by the provider implementation; consult the provider module for the registry before referencing one.

### 5.5 `failure_message`

Shown to the learner when a check fails. Make it:

* **Actionable:** name the next command to try (`start it with virsh start lab-vm`).
* **Honest:** distinguish "not done yet" from "environment problem".
* **Secret-free:** never include endpoints, VMIDs, tokens, or internal paths of the *provider* deployment.

### 5.6 Ordering within a step

Cheap readiness checks → objective state checks → knowledge checks → attestations. Learners see and complete checks in order, so gate slow work behind fast gates.

---

## 6. Environments, scopes, and capabilities

```yaml
environment:
  scope: course            # course | lesson | none
  provider_capability: proxmox.vm
  guest_capabilities:
    - os.nixos
    - tool.curl
```

| Scope | Behavior | Use when |
|---|---|---|
| `course` | One disposable environment reused across the course | Lessons build on each other (our NixOS example) |
| `lesson` | Each lesson gets its own environment; switching lessons shows the recorded VM and **requires confirmation** before replacement | Lessons are destructive or need clean state |
| `none` | No provider, no secret resolution | Purely conceptual courses |

Authoring constraints:

* With `scope: none`, `remote-command` and `provider-check` are **forbidden** (the loader errors); use `text-evidence` and `manual-confirmation` only.
* `provider_capability` is **required** for `course`/`lesson` scopes and **forbidden** for `none`.
* `guest_capabilities` is optional for VM scopes and forbidden for `none`.
  Declare the OS and tools that commands require. Validation warns when a VM
  policy has no `os.*` capability or a recognized command tool is undeclared.
* A lesson may supply its own `environment:` block. The lesson block replaces
  the complete course policy; fields are not merged. Repeat every required
  provider and guest capability in the override.
* The legacy top-level `requirements` list is accepted only while migrating. It
  is mapped to `environment.guest_capabilities`, emits one warning per course,
  cannot be combined with that new field, and is planned for removal. New and
  edited courses must use `guest_capabilities`.

Operational behavior authors should understand (so they can write good instructions and failure messages):

* An environment is reused only when its recorded profile, provider fingerprint, endpoint, VMID, and expected VM name all match. Any mismatch **fails closed** and points at the destroy/recovery path.
* Lesson-scoped replacement is never implicit: declining the confirmation keeps the existing VM and progress.
* Course content must never supply provider profiles, endpoints, URLs, VMIDs,
  template IDs or names, nodes, storage, networks, SSH identity paths, token
  identities, or secrets. Curriculum declares only scopes and capabilities;
  the learner's named profile supplies provider values.

---

## 7. Security and content rules

1. **No secrets, ever.** Never place tokens, secret values, endpoints, VMIDs, node names, or other deployment data in curriculum YAML, instructions, prompts, or failure messages. Secrets belong only in the environment variable named by `token_secret_env` in the learner's own config.
2. **Learner text is never executed.** Design knowledge assessment with `text-evidence`; do not build "type a command for the platform to run" flows.
3. **Curriculum commands are production code.** Every `remote-command` runs on a real VM. Quote carefully, avoid `rm -rf`-style patterns, prefer `test`/`grep -q`, and scope any mutation to learner-owned artifacts.
4. **Bounded everything.** ≤ 300 s timeout, small output, non-interactive, no hangs.
5. **Least-privilege teaching.** Like the shipped `api-tokens` lesson, teach dedicated identities and least privilege *conceptually* inside the course environment; never have learners change provider permissions mid-course.
6. **Honest attestations.** `manual-confirmation` is labeled self-attestation in provenance; don't launder it as objective verification.

---

## 8. Testing your course

### 8.1 Maturity and digest-bound certification

Every course has one of three maturity values:

| Maturity | Meaning | Start behavior |
|---|---|---|
| `draft` | The default for an unproven course | A new session requires `--include-drafts` |
| `offline-validated` | Structural and recorded offline review passed for these exact course files | Still requires `--include-drafts`; this is not live proof |
| `live-validated` | The full live acceptance protocol passed for these exact course files | May be started without the draft opt-in |

Maturity comes from `src/learnlab/collections/certifications.yaml`. A record is
valid only for the SHA-256 digest of the complete course directory: sorted
relative file paths and every file's bytes are included. A missing record or a
stale digest always resolves to `draft`. This fail-closed rule means any edit
to `course.yaml`, a lesson, or another file under the course directory removes
the effective certification until the changed course is reviewed again.

Each registry entry has exactly these fields:

```yaml
certifications:
  - path: example/example-course
    digest: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    status: offline-validated
    validated_at: 2026-09-10
    learnlab_revision: git-revision-reviewed
    guest_capabilities:
      - os.debian.13
      - tool.curl
    note: Short description of the review performed.
```

Records contain review facts only. Review their exact schema and content before
committing. Never record a provider profile, endpoint or URL, VMID, node, IP
address, token, credential, template or other personal infrastructure value.
The recorded `guest_capabilities` must describe the capabilities reviewed for
that course digest; profile declarations remain assertions and are not proof
that a guest contains them.

### 8.2 Offline validation

Run validation from the repository root after every curriculum edit. With no
course argument it discovers and checks the entire canonical packaged catalog;
pass `collection/course` to select one course.

```bash
learnlab validate
learnlab validate nixos/vm-management
learnlab validate nixos/vm-management --format json
```

Offline validation loads no settings or state database, resolves no secrets,
and makes no SSH, network, or provider calls. It reports all independent schema,
layout, capability, regular-expression, and authoring-lint findings it can find.
Warnings are advisory and still exit `0`.

Exit codes are stable for scripts:

| Code | Meaning |
|---|---|
| `0` | No curriculum errors; warnings may be present |
| `1` | Curriculum or capability findings contain an error |
| `2` | Invalid command usage or option value |
| `3` | Provider configuration, secret resolution, access, or health failed in online mode |

JSON output uses this exact schema-v1 shape. The root has exactly these three
fields, and each finding has exactly these six fields:

```json
{
  "schema_version": 1,
  "ok": true,
  "findings": [
    {
      "severity": "warning",
      "course_path": "nixos/vm-management",
      "source_path": "nixos/courses/vm-management/course.yaml",
      "code": "missing-os-capability",
      "message": "A VM environment does not declare an OS guest capability.",
      "remedy": "Declare the required os.* capability for the effective environment."
    }
  ]
}
```

`schema_version` is the integer `1`; `ok` is a boolean; `findings` is an array.
Finding `severity` is `error` or `warning`; every other finding field is a
string. Paths are relative to `src/learnlab/collections/`. Output is
deterministically ordered and contains neither secrets nor raw provider data.

Passing offline validation can support an `offline-validated` review record,
but it does not exercise a provider, guest, lesson command, progress flow, or
cleanup. Keep the course draft unless the repository's review process actually
creates a matching record.

### 8.3 Repository test suite

Normal tests are offline and must not connect to Proxmox:

```bash
python3.13 -m pytest -m 'not live' -q
```

Mirror the style of `tests/test_curriculum.py` when adding loader fixtures for new edge cases.

### 8.4 Read-only provider validation

After offline validation succeeds, an explicit profile can check whether its
declared template capabilities cover the effective course requirements and can
run the existing provider health inspection:

```bash
learnlab validate nixos/vm-management --provider scratch-profile
learnlab validate --provider scratch-profile --format json
```

This mode resolves only the named profile and its secret, then calls the
read-only health check for API access, template identity, node, storage, and
network. It never allocates, clones, starts, stops, reconfigures, or deletes a
resource. A passing result proves only that the profile declares the required
capabilities and that these health checks passed at that moment. Capability
declarations are configuration assertions; they do not prove installed guest
software or live course behavior.

The walkthrough in this guide remains unverified until separately exercised
and reviewed. `learnlab validate` never claims live acceptance or course
certification.

### 8.5 Live acceptance and certification

Live acceptance is a separate, opt-in validation level. It provisions and
destroys real course environments, so obtain explicit approval for the exact
course and a named **scratch profile** before starting. Confirm that the fresh
template declares the course's guest capabilities. Run courses serially when
they share infrastructure, and never broaden provider permissions merely to
make acceptance pass.

For each approved course:

1. Run offline validation, then read-only provider validation against the
   intended scratch profile.
2. Start from a fresh compatible template using `--include-drafts`.
3. Complete every lesson and verification in order.
4. Intentionally fail at least one check and assess whether its remediation
   message is accurate and actionable.
5. Save and exit mid-lesson, then resume at the first incomplete check.
6. Confirm the expected cumulative course state after all lessons.
7. Destroy the scratch environment through LearnLab and verify that it is
   absent.
8. Add a certification record only after cleanup succeeds, or after any
   uncertain cleanup state has been reconciled against provider inventory.

An interruption or timeout can leave infrastructure in an uncertain state.
Preserve LearnLab state and recovery guidance, inspect ownership before retrying,
and never delete a resource by VMID alone. Failed or unverified cleanup blocks
certification. Record the matching digest only after content stops changing;
rerun the repository gates and review the record for secrets before committing.

The six nginx, nftables, and systemd courses added during the pending-course
review are canonical but remain draft: their live acceptance has not been
performed. nftables NAT is deliberately deferred to a future multi-machine
workstream rather than weakened into manual confirmation.

### 8.6 Optional live lifecycle test for provider code

If you add provider inspection names or lifecycle behavior, the intentionally
destructive provider lifecycle test (`tests/live/test_proxmox_lifecycle.py`)
runs only when both `LEARNLAB_RUN_LIVE_PROXMOX=1` and
`LEARNLAB_LIVE_PROFILE=<profile>` are set, with the profile secret already
exported. Never enable it casually. Passing this provider test alone does not
complete the course acceptance checklist or certify curriculum.

---

## 9. Shipping and versioning

* **IDs are forever.** Progress, resumes, and administrative overrides reference paths like `proxmox/proxmox-admin/api-access`. Renaming a shipped collection/course/lesson/step/verification id orphans recorded progress. Add new ids; don't rename.
* **Any course-file edit invalidates certification.** Improving instructions, prompts, regexes, and failure messages under stable ids is normal, but it changes the digest and makes the course effectively `draft` until it is reviewed and recorded again.
* **Renumbering directories is safe** (ordering lives in `course.yaml`) but pointless churn; keep prefixes stable.
* **Appending lessons preserves old completion rows but changes the digest.** Existing learners resume at their first incomplete lesson after the new content becomes startable; recertify the changed course before treating it as ready.
* **Maturity does not rewrite progress.** Certification controls whether a new `start` needs `--include-drafts`; it does not erase recorded checks or turn prior progress into evidence for a changed digest. `resume` still requires existing local course state.
* **`learnlab progress complete …` is an administrative override**, recorded as `manual_override`. Never instruct learners to use it; it exists for exceptional recovery and course administration only.

---

## 10. Troubleshooting

### 10.1 Loader errors

| Error (paraphrased) | Cause | Fix |
|---|---|---|
| `missing keys: …; unknown keys: …` | Exact-key violation | Match the key tables in §3.2 / Appendix A |
| `ID does not match directory` | `id` ≠ directory (or lesson dir suffix) | Align ids and directory names |
| `expected one lesson directory for X` | Zero or multiple `*-X` dirs | Exactly one `<NN>-<lesson-id>` dir per id |
| `forbidden fields for remote-command: prompt` | Mixed type fields | Use only the fields for that type |
| `text-evidence requires exactly one of equals or matches` | Both or neither present | Pick one |
| `invalid regular expression` | Bad Python regex in `matches` | Test with `python3 -c "import re; re.compile(...)"` |
| `timeout_seconds must be an integer from 1 to 300` | Out-of-range/bool/string | Use an int in 1–300 |
| `remote-command requires an environment` | Check under `scope: none` | Change scope or use text-evidence |
| `provider_capability is forbidden for none environment scope` | Capability with `none` | Remove it |
| `Course path must use collection/course` | Bad CLI path or ids | Use `collection/course` with stable ids |

### 10.2 Runtime symptoms

| Symptom | Likely cause | Fix |
|---|---|---|
| Check fails though the work is done | Command exits nonzero / output-based thinking | Rewrite as exit-status assertion (`test`, `grep -qx`, `--quiet`) |
| Check times out | Interactive prompt, unbounded command, slow op | Add flags (`-c`, `-W`), raise `timeout_seconds` ≤ 300 |
| Flaky pass/fail on resume | Non-idempotent check | Make re-runs stable |
| `sudo:` prompt hang | Password sudo over batch SSH | Design checks that don't need sudo, or passwordless template |
| Environment reuse refused | Profile/VM fingerprint mismatch (fail-closed) | Follow the destroy/recovery path; never delete by VMID alone |

---

## Appendix A: schema reference

**`collection.yaml`** — exact keys: `id`, `title`.

**`course.yaml`** — exact keys: `id`, `title`, `lessons`, `environment`;
legacy `requirements` is temporarily optional only as the migration input
described in §6.

**`lesson.yaml`** — exact keys: `id`, `title`, `steps`; optional `environment` (override).

**step** — exact keys: `id`, `title`, `instructions`|`content`, `verifications` (non-empty).

**environment** — `scope` (`course|lesson|none`) is required. For `course` and
`lesson`, `provider_capability` is required and `guest_capabilities` is an
optional list of unique capability IDs. For `none`, both capability fields are
forbidden. A lesson environment is a complete replacement policy.

**verification** — common: `id`, `type`, `failure_message?`; typed:

| type | required | optional |
|---|---|---|
| `remote-command` | `command` | `timeout_seconds` (int 1–300, default 30) |
| `text-evidence` | `prompt`, one of `equals`/`matches` | — |
| `manual-confirmation` | `prompt` | — |
| `provider-check` | `check` | — |

---

## Appendix B: CLI quick reference

```bash
learnlab provider test home-proxmox                 # read-only profile health check
learnlab validate                                   # offline, complete catalog
learnlab validate <collection>/<course>             # offline, one course
learnlab validate <collection>/<course> --format json
learnlab validate <collection>/<course> --provider p # read-only online checks
learnlab start nixos/vm-management --provider p --include-drafts # uncertified example
learnlab resume nixos/vm-management --provider p    # explicit resume
learnlab progress                                   # view recorded state
learnlab progress complete <c>/<course>/<lesson>    # admin override (provenance: manual_override)
learnlab reset <scope> [--yes]                      # reset scope; refuses if env must be destroyed first
learnlab destroy                                    # interactive, lists targets
learnlab destroy --yes --preserve-progress          # non-interactive, exactly one policy flag
learnlab destroy --yes --erase-progress
```

Config lives at `~/.config/learnlab/config.toml`; secrets only via the env var named in `token_secret_env`; keep `tls_verify = true` outside private labs.

---

## Appendix C: pre-ship checklist

- [ ] All ids stable, lowercase-hyphenated, unique within parent
- [ ] Directory names match ids; exactly one dir per lesson id
- [ ] Exact keys only; `instructions`/`content` not both
- [ ] Every step has ≥ 1 verification; order = readiness → objective → knowledge → attestation
- [ ] Every `remote-command`: exit-status based, idempotent, non-interactive, quiet, absolute paths, bounded runtime
- [ ] Every `text-evidence`: answer derivable from instructions; regex compiles; `equals` only for short tokens
- [ ] `manual-confirmation` used only for genuine self-attestation
- [ ] `provider-check` names exist in the provider registry; readiness gates precede first SSH check
- [ ] Scope chosen deliberately; provider and guest capability IDs declared; lesson overrides repeat the complete policy; `none` courses contain no remote/provider checks
- [ ] No new `requirements`; legacy courses migrated to `environment.guest_capabilities`
- [ ] No secrets, endpoints, VMIDs, or deployment values anywhere in content
- [ ] `failure_message`s actionable and secret-free
- [ ] `learnlab validate` and the selected-course JSON command (§8.2) pass
- [ ] Read-only profile validation (§8.4), when relevant, passes without being treated as live proof
- [ ] Maturity record matches the final course digest and contains only non-secret review facts
- [ ] Eight-point live acceptance (§8.5) completed before using `live-validated`
- [ ] `pytest -m 'not live' -q` passes
