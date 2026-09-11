# NixOS Template Bootstrap Course Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver `proxmox/nixos-template`, a guided ISO-to-template bootstrap course with the standalone guide and honest two-clone acceptance protocol.

**Architecture:** Use existing NONE-scope sessions, self-attested runtime checkpoints and exact-token knowledge checks. Learners operate their own Proxmox/guest consoles; the engine performs no image build, adoption or infrastructure mutation. Output capabilities are documented template properties, not dependencies of the bootstrap course.

**Tech Stack:** Python 3.13, YAML, pytest, Typer, existing curriculum/session/validation services, Proxmox UI/node shell, NixOS 26.05 installer.

**Spec:** `docs/superpowers/specs/2026-09-10-nixos-template-course-design.md`

**Status:** Tasks 1–4 and Task 5 offline Steps 1–3 completed on 2026-09-11. Course remains draft; live acceptance and final whole-branch review remain pending. See [offline acceptance evidence](../../course-validation/2026-09-10-nixos-template.md).

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

## Execution context and preflight

Start from current `main` containing `287d350` (pending-course implementation), not an old checkout. Create or reuse an isolated worktree, install dev dependencies in its `.venv`, and run `.venv/bin/python -m pytest -m 'not live' -q`. Never reuse a venv entry point that imports a sibling checkout; use `PYTHONPATH=src` for CLI smoke checks if using a shared interpreter. The current main baseline was 513 passed, 1 deselected; discover the current count rather than asserting that historical count.

Read the spec and `docs/LearnLab-Course-Authoring-Guide.md`. Existing interfaces are `CurriculumCatalog(Path).load_course(path)`, `Course.effective_environment(lesson)`, `Course.maturity`, `validate_catalog(catalog, course_path)`, and `course_digest(course_dir)`. No new production API is required. Verify `learnlab provider test --help`: its profile name is positional. `learnlab validate COURSE --provider PROFILE` has a flag. Resume has no `--include-drafts` flag.

The sibling bootstrap course may already be merged. Preserve its content and adapt shared tests conditionally; neither task depends on the other. Do not change the existing proxmox collection ID/title or introduce a course list into its strict schema. Keep each task commit and review independent. Task reports should record real RED/GREEN commands and evidence, not invented failures.

## File map

- `src/learnlab/collections/proxmox/courses/nixos-template/course.yaml`: ordered manifest.
- `src/learnlab/collections/proxmox/courses/nixos-template/lessons/00-prerequisites-and-safety/lesson.yaml`: prerequisites-and-safety lesson.
- `src/learnlab/collections/proxmox/courses/nixos-template/lessons/01-create-installer-vm/lesson.yaml`: create-installer-vm lesson.
- `src/learnlab/collections/proxmox/courses/nixos-template/lessons/02-install-nixos/lesson.yaml`: install-nixos lesson.
- `src/learnlab/collections/proxmox/courses/nixos-template/lessons/03-configure-lab-access/lesson.yaml`: configure-lab-access lesson.
- `src/learnlab/collections/proxmox/courses/nixos-template/lessons/04-seal-and-convert/lesson.yaml`: seal-and-convert lesson.
- `src/learnlab/collections/proxmox/courses/nixos-template/lessons/05-test-two-clones/lesson.yaml`: test-two-clones lesson.
- `src/learnlab/collections/proxmox/courses/nixos-template/lessons/06-configure-provider/lesson.yaml`: configure-provider lesson.
- `tests/test_nixos_template_course.py`: course-specific contracts and negative knowledge-answer coverage.
- `tests/test_shipped_course_metadata.py`: NONE versus VM metadata invariant.
- `tests/test_cli.py`: no-profile start/resume isolation using actual packaged curriculum.
- `tests/test_packaging.py`: extend existing wheel build/install smoke, not another wheel build.
- `docs/NixOS-Template-Guide.md`: standalone detailed guide, including all seven phases.
- `docs/course-validation/2026-09-10-nixos-template.md`: non-secret offline/live acceptance report.
- `README.md`: guide link and no-profile bootstrap command.

---

### Task 1: Real introductory lesson and no-profile boundary

**Files:** Create `src/learnlab/collections/proxmox/courses/nixos-template/course.yaml`, `src/learnlab/collections/proxmox/courses/nixos-template/lessons/00-prerequisites-and-safety/lesson.yaml`, `tests/test_nixos_template_course.py`; modify `tests/test_shipped_course_metadata.py` and `tests/test_cli.py`.

**Interfaces:** Produces `COURSE_PATH`, `ROOT`, `load_course()` and `lesson_text(lesson_id)` in the course test file for later tests. Consumes existing NONE-scope engine; no provider API additions.

- [x] **Step 1: Add course loading/boundary regression tests.** Use these imports/helpers and tests in `tests/test_nixos_template_course.py`:

```python
from pathlib import Path

from learnlab.course_certification import CourseMaturity
from learnlab.course_validation import validate_catalog
from learnlab.curriculum import CurriculumCatalog, EnvironmentScope, VerificationType

ROOT = Path(__file__).parents[1] / "src/learnlab/collections"
COURSE_PATH = "proxmox/nixos-template"

def load_course():
    return CurriculumCatalog(ROOT).load_course(COURSE_PATH)

def lesson_text(lesson_id):
    lesson = next(item for item in load_course().lessons if item.id == lesson_id)
    return "\n".join(step.instructions for step in lesson.steps)

def test_bootstrap_has_no_managed_environment():
    course = load_course()
    assert course.maturity is CourseMaturity.DRAFT
    assert course.lessons[0].id == "prerequisites-and-safety"
    for lesson in course.lessons:
        policy = course.effective_environment(lesson)
        assert policy.scope is EnvironmentScope.NONE
        assert policy.provider_capability is None
        assert policy.guest_capabilities == ()
        for step in lesson.steps:
            assert step.verifications
            assert all(v.type in {VerificationType.TEXT_EVIDENCE,
                                  VerificationType.MANUAL_CONFIRMATION}
                       for v in step.verifications)

def test_bootstrap_validates_without_findings():
    report = validate_catalog(CurriculumCatalog(ROOT), COURSE_PATH)
    assert report.ok
    assert report.findings == ()
```

- [x] **Step 2: Run RED.** `.venv/bin/python -m pytest tests/test_nixos_template_course.py -q`; expected missing-course failure, not a collection/import error.

- [x] **Step 3: Create a working one-lesson course, not empty future lessons.** Initial manifest:

```yaml
id: nixos-template
title: Build a NixOS 26.05 Template for LearnLab
environment:
  scope: none
lessons:
  - prerequisites-and-safety
```

The first lesson explains controller versus node versus guest, owner-only worksheet, no-profile start, manual progress limitations, safe stop/resume and no automatic cleanup. Include an exact-token knowledge step of this shape, with its own execution-attestation step if needed:

```yaml
id: prerequisites-and-safety
title: Prerequisites and Safety
steps:
  - id: understand-ownership
    title: Who operates the infrastructure?
    instructions: |
      Controller: LearnLab records progress. You operate Proxmox and the guest
      explicitly. A saved lesson does not prove that a VM still exists or owns
      the same ID. Inspect your local resource worksheet before resuming.
    verifications:
      - id: infrastructure-owner
        type: text-evidence
        prompt: 'Who operates the infrastructure here? Enter learner or learnlab.'
        equals: learner
        failure_message: The learner operates Proxmox; LearnLab only guides this course.
```

- [x] **Step 4: Correct the shared metadata assumption without weakening VM coverage.** Import `EnvironmentScope` in `tests/test_shipped_course_metadata.py`; replace its unconditional nonempty capability assertion with:

```python
for lesson in course.lessons:
    policy = course.effective_environment(lesson)
    if policy.scope is EnvironmentScope.NONE:
        assert policy.provider_capability is None
        assert policy.guest_capabilities == ()
    else:
        assert policy.guest_capabilities
        assert len(set(policy.guest_capabilities)) == len(policy.guest_capabilities)
```

If a sibling course already made this correction, reuse it. Do not delete all-shipped coverage or alter the six pending-course set.

- [x] **Step 5: Exercise real CLI startup with no profile.** Add a test in `tests/test_cli.py` using its existing `tmp_xdg` fixture and `CliRunner`. Patch `cli.load_settings`, `cli.resolve_token_secret`, `cli.provider_factory` to a function that raises `AssertionError`; start `["start", "proxmox/nixos-template", "--include-drafts"]`, answer the first concept correctly, then save and exit. Assert exit 0, NONE policy, saved progress, no configuration access. Use the actual prompt sequence (inspect `ConsoleSessionPrompt`); do not replace the course/session with a synthetic fake. Add a resume assertion for the saved session with the same tripwires and no provider flag.

- [x] **Step 6: GREEN and commit.** Run `tests/test_nixos_template_course.py`, `tests/test_shipped_course_metadata.py` and the new CLI test. Commit only these files and the manifest/first lesson with subject `feat: add nixos-template bootstrap entry course`.

### Task 2: Installer and lab access lessons

**Files:** Add `src/learnlab/collections/proxmox/courses/nixos-template/lessons/01-create-installer-vm/lesson.yaml`, `src/learnlab/collections/proxmox/courses/nixos-template/lessons/02-install-nixos/lesson.yaml`, `src/learnlab/collections/proxmox/courses/nixos-template/lessons/03-configure-lab-access/lesson.yaml`; extend manifest and `tests/test_nixos_template_course.py`; begin `docs/NixOS-Template-Guide.md` with these completed sections.

**Interfaces:** Consumes test helpers from Task 1. Produces installable guest and confirmed controller key/sudo/agent/tool access as learner-verified checkpoints; nothing is entered into engine environment state.

- [x] **Step 1: Add RED tests for the new instructional contract.** Add to `tests/test_nixos_template_course.py`:

```python
def test_installer_teaches_target_specific_steps():
    text = lesson_text("install-nixos")
    for concept in ['nixos-generate-config', 'nixos-install', 'hardware-configuration.nix', 'system.stateVersion']:
        assert concept.lower() in text.lower()
    assert "Installer console" in text
    assert "disk" in text.lower() and "confirm" in text.lower()

def test_access_covers_required_guest_configuration():
    text = lesson_text("configure-lab-access")
    for concept in ['services.qemuGuest.enable', 'services.openssh.enable', 'environment.systemPackages', 'nixos-rebuild test']:
        assert concept in text
    assert "private key" in text.lower()
    assert "public key" in text.lower()
```

Run `.venv/bin/python -m pytest tests/test_nixos_template_course.py -q`; expect missing lesson failures. These are content regressions, not proof of guest execution.

- [x] **Step 2: Write installer lessons using the spec's Installation design.** Include the full Proxmox UI settings, verified official minimal x86_64 ISO, HTTPS/checksum verification, networking diagnostics, actual disk identification, confirmation before writes, OS installation and disk-only boot. Treat installer UI, editor and password entry as deliberately interactive learner actions, not remote verifications. After each action specify expected state, how to diagnose a mismatch and where to stop. There must be no unconditional disk-format command that can be copied before identity confirmation.

- [x] **Step 3: Write the access lesson using the spec's Lab access design.** Cover guest agent at both hypervisor and guest, actual tool packages, trusted SSH enrollment, key login before disabling password SSH, checked lab-only sudo policy and a separate console recovery route. Derive downstream template capabilities with this read-only developer command:

```bash
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

Map that list to actual installed commands in the guide. Leave unrelated exercise state absent. Add new IDs to the manifest only when their complete lessons exist. Keep manual attestations in separate steps from knowledge questions.

- [x] **Step 4: Add knowledge-answer cases and verify.** For each added text check, table a known accepted concept and at least one negated/unrelated answer. Execute the actual `equals` or full regex against those examples; never just assert that a regex string contains anchors. Test YAML with `validate_catalog`; run `.venv/bin/learnlab validate proxmox/nixos-template` and focused pytest. Review instructions and shell snippets without running guest commands.

- [x] **Step 5: Commit the installer/access lessons, guide sections and tests.** Subject: `feat: teach nixos-template installation and lab access`.

### Task 3: Safe sealing and two-clone identity acceptance

**Files:** Add `src/learnlab/collections/proxmox/courses/nixos-template/lessons/04-seal-and-convert/lesson.yaml`, `src/learnlab/collections/proxmox/courses/nixos-template/lessons/05-test-two-clones/lesson.yaml`; extend manifest, guide and `tests/test_nixos_template_course.py`.

**Interfaces:** Consumes learner-owned installed guest. Produces a retained template and two learner-owned test clones, not LearnLab-managed environments. No new lifecycle methods or validators.

- [x] **Step 1: Add RED safety regressions.** In `tests/test_nixos_template_course.py`:

```python
def test_sealing_and_clone_identity_contract():
    seal = lesson_text("seal-and-convert").lower()
    clones = lesson_text("test-two-clones").lower()
    assert "snapshot" in seal and "console" in seal
    assert "do not reboot" in seal
    assert "/etc/machine-id" in seal
    assert "/var/lib/dbus/machine-id" in seal
    assert "two" in clones and "full clones" in clones
    assert "distinct" in clones and "stable" in clones
    assert "known_hosts" in clones
    assert "ssh-keyscan alone" in clones
```

Run focused tests; expect missing lessons. Add OS-specific regression cases for the sealing design, including the NixOS hostKeys/generated sshd inspection.

- [x] **Step 2: Implement the spec's OS-specific sealing phase.** Give inspect/confirm/execute/verify checkpoints. Check actual file types/mounts and D-Bus fallback; do not introduce a universal rm/truncate script for arbitrary paths. Preserve already working templates, require no snapshots before conversion, and explain interruption recovery. No automatic snapshot deletion, force flags or reboot after sealing. Never mutate the template currently used by another profile.

- [x] **Step 3: Implement two-clone acceptance instructions.** Each clone must boot from disk, have confirmed guest agent/SSH/sudo/tool access, and have its own machine ID and host keys. Verify A differs from B and each is stable after a reboot. Require console-authenticated host-key enrollment into an isolated file. Ask the learner only to confirm local comparison results; never persist raw identities or addresses. Include the OS-specific configuration check from the spec.

- [x] **Step 4: Test any introduced guard logic without real resources.** For a shell guard, use PATH stubs under `tmp_path` and an invocation log. Cover ID collision, wrong resource name/template flag, failed lookup, timeout, already-converted candidate and partially cleaned clone. Assert no mutating stub is called until ownership and explicit confirmation pass; failed lookup must not be treated as absence. If no executable helper is introduced, do not invent one for testing: record this as manual-instruction coverage and keep live acceptance pending.

- [x] **Step 5: GREEN, review and commit.** Run focused tests and offline validation. Subject: `feat: teach safe nixos-template sealing and clone checks`.

### Task 4: Profile handoff, complete guide and installed-wheel coverage

**Files:** Add `src/learnlab/collections/proxmox/courses/nixos-template/lessons/06-configure-provider/lesson.yaml`; finish manifest, guide and `tests/test_nixos_template_course.py`; modify `README.md`, `tests/test_packaging.py`, and extend no-profile CLI coverage from Task 1 as needed.

**Interfaces:** Produces the final seven-lesson course. Learner creates a new named `ProxmoxProfile` using the existing schema. Read-only provider health and downstream compatibility are learner-invoked only after setup; no profile is loaded by the course session itself.

- [x] **Step 1: Add RED final-order and cleanup-boundary tests.**

```python
def test_complete_lesson_order_and_handoff():
    assert [lesson.id for lesson in load_course().lessons] == ['prerequisites-and-safety', 'create-installer-vm', 'install-nixos', 'configure-lab-access', 'seal-and-convert', 'test-two-clones', 'configure-provider']
    handoff = lesson_text("configure-provider")
    assert 'learnlab provider test "$PROFILE"' in handoff
    assert "template_capabilities" in handoff
    assert "learner-owned" in handoff
    assert "not" in handoff.lower() and "learnlab destroy" in handoff
    assert "absence" in handoff.lower()
```

Run focused tests; expect missing final lesson/order mismatch. Supplement this token check with review of the actual prohibition: LearnLab cannot destroy untracked clones.

- [x] **Step 2: Complete handoff and cleanup instructions.** Explain all current profile fields by adapting the existing README schema to local learner inputs; leave real values out of the course. Preserve existing profiles/defaults and store only the secret environment-variable name. Teach positional `learnlab provider test "$PROFILE"` and `learnlab validate COURSE --provider "$PROFILE"` for matching nginx/nftables/systemd paths. Distinguish compatibility assertions from live success and clone permission testing. Clean up only the two learner-owned test clones through Proxmox after full identity/confirmation checks; verify absence, retain template and source, and stop on uncertainty. Do not execute any of these commands during offline tests.

- [x] **Step 3: Finish standalone guide and README entry.** The guide contains all course steps, terminal labels, actual commands, expected output and concrete troubleshooting. Cite the primary references listed in the spec, record version assumptions, and explicitly label untested procedures. README links it and shows `learnlab start proxmox/nixos-template --include-drafts` without a provider. Distinguish template creation from downstream live course certification.

- [x] **Step 4: Extend the existing wheel test without building twice.** In the already-installed wheel subprocess in `tests/test_packaging.py`, load this course from `files("learnlab") / "collections"`, assert NONE/empty dependencies and draft maturity, and run a start/save/resume smoke with forbidden settings/provider access. Preserve all six pending-course checks and any sibling bootstrap checks. In `tests/test_cli.py`, verify no-profile course progress survives save/resume and that runtime results remain self-attested, not a live-certificate grant. Do not delete unrelated CLI fixtures or bypass draft gating globally.

- [x] **Step 5: GREEN and commit.** Run focused course tests, relevant CLI tests, `tests/test_packaging.py`, and offline validation. Subject: `docs: finish nixos-template provider handoff and guide`.

### Task 5: Full offline gate, review and optional live acceptance

**Files:** Create `docs/course-validation/2026-09-10-nixos-template.md`; update this plan's checked steps only when completed. Modify `src/learnlab/collections/certifications.yaml` only after an approved successful live run.

**Interfaces:** Consumes final course contents, `course_digest`, existing strict certification schema and all prior task evidence. Produces an honest acceptance report and either draft status with blockers or an exact-digest live record.

- [x] **Step 1: Run and record full offline verification.**

```bash
.venv/bin/python -m pytest -m 'not live' -q
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/learnlab validate proxmox/nixos-template
git diff --check
```

The full suite includes wheel build/install. Do not rerun packaging without a new relevant change. Review each lesson against the spec, including every destructive checkpoint and each negative knowledge case. Keep the three pre-existing proxmox-admin warnings separate from any new course finding; do not update snapshots to hide a new warning.

- [x] **Step 2: Record final digest and non-secret blockers.**

```bash
PYTHONPATH=src .venv/bin/python - <<'DIGEST'
from pathlib import Path
from learnlab.course_certification import course_digest
print(course_digest(Path("src/learnlab/collections/proxmox/courses/nixos-template")))
DIGEST
```

Record actual date/revision, offline commands/results, exact digest, OS/ISO version assumptions and all untested live steps. Do not record worksheet values, private material or raw clone identities. Recalculate if any course file changes after review.

- [x] **Step 3: Stop before live resource actions unless separately authorized.** Present exact scratch candidate/template/clone identities, expected storage/network effects and cleanup/retention behavior to the operator privately. Approval to implement curriculum is not approval to partition, create, seal, convert or delete resources. If no live authorization, leave the registry untouched, report draft blockers and finish the offline implementation without pretending live completion.

- [ ] **Step 4: If approved, complete the seven-lesson live traversal.** Fresh ISO installation; intentional safe failure and remediation; save/resume; successful sealing; two full clones with distinct identities; per-clone reboot identity stability; guest access/tool/configuration checks; profile health/compatibility; stop/destroy only test clones and verify absence while retaining intended template. Checkpoints remain pending until observed. An uncertain result blocks certification and requires reconciliation. The course engine must still make zero provider/SSH calls during its session.

- [x] **Step 5: Review and commit the truthful outcome.** After an approved complete run, add only existing registry fields with a digest-matched record and concise non-secret note. Otherwise commit the draft acceptance report without a registry entry. Request final whole-branch review, resolve findings, run covering checks after fixes, then report preserved branch/worktree and remaining live gates. Suggested commit subject for offline-only outcome: `docs: record nixos-template offline acceptance and live blockers`. No implicit merge or push.
