# Proxmox Provider Bootstrap Course Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a draft, provider-free course that safely guides an authorized learner through creating, validating, live-accepting, and optionally revoking the exact named Proxmox provider profile LearnLab already supports.

**Architecture:** The feature is curriculum-first: eight packaged `EnvironmentScope.NONE` lessons display learner-operated instructions and record only text answers or self-attestation. Focused content tests lock the code-derived provider surface and safety boundaries, while real CLI and installed-wheel tests prove that starting, saving, and resuming the draft never load settings, secrets, provider, SSH, or network dependencies. Documentation gains only the optional cross-link and the narrowly defined NONE-scope authoring exception; provider, lifecycle, configuration, state, and certification code remain unchanged.

**Tech Stack:** Python 3.13, PyYAML curriculum, Typer `CliRunner`, pytest, Ruff, mypy, Hatchling wheel packaging, Markdown.

**Spec:** `docs/superpowers/specs/2026-09-11-proxmox-provider-bootstrap-design.md`

## Global Constraints

- Work only in the existing isolated `feature/nixos-template-course` worktree and preserve unrelated user changes.
- Tasks 1–5 and 7 use TDD: add the focused failing assertion, observe the expected failure, add the minimum complete curriculum or documentation needed, then rerun the focused gate. Task 6 is the sole exception because it adds only post-feature source/install characterization tests; those tests must pass on first execution and do not claim a RED phase.
- Dispatch a fresh implementation sub-agent for each task and run both a spec-compliance review and a code-quality review before accepting that task.
- Keep `proxmox/provider-bootstrap` at `environment.scope: none`; every effective environment has no provider capability and no guest capabilities.
- The course may use only `text-evidence` and `manual-confirmation`; it may not contain `remote-command`, `provider-check`, or any LearnLab-executed operation.
- Every lesson begins with prerequisites, a resume/reinspection rule, named execution locations, expected outcomes, stop conditions, and at least one concrete troubleshooting branch.
- Keep lesson, step, and verification IDs stable once introduced; keep conceptual answers separate from action attestations so a manual confirmation does not duplicate a knowledge check.
- Ordinary course execution must make zero settings, selected-profile, secret-resolution, provider, SSH, HTTP, or other network calls.
- Do not change `src/learnlab/providers/proxmox.py`, `src/learnlab/lifecycle.py`, profile parsing, secret resolution, CLI behavior, state schemas, or live tests.
- Do not change `proxmox/proxmox-admin` or its digest.
- Do not edit `src/learnlab/collections/certifications.yaml`; the new course and the changed NixOS course must fail closed to `draft` without exact-digest records.
- Do not add provider pool placement, pool-aware allocation, privilege automation, or infrastructure mutation.
- Keep all Proxmox privilege mappings labeled `installed-version/live-confirmation-required`; repository tests prove coverage and wording, not portable permission semantics.
- Preserve the accepted propagated `/vms` limitation and make its broader-than-pool scope conspicuous.
- Do not put secrets or deployment-specific endpoints, hostnames, VMIDs, usernames, token identities, resource paths, fingerprints, task IDs, or inventory output in curriculum, progress, tests, shared evidence, or the offline report.
- Permit non-secret deployment identifiers only in the learner's private profile, private worksheet, and isolated lifecycle ownership state where runtime and cleanup require them.
- Keep the existing profile/default intact; the new course teaches an additional explicitly named profile and an external hidden mechanism that populates the environment variable named by `token_secret_env`.
- Live resource work, permission changes, lifecycle acceptance, cleanup, rollback, and certification are outside implementation. Stop after the offline gate and request a new explicit authorization before executing the documented live protocol.

## File Map

- `src/learnlab/collections/proxmox/courses/provider-bootstrap/course.yaml`: owns the course ID, title, NONE environment, and exact eight-lesson order.
- `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/00-safety-and-private-worksheet/lesson.yaml`: private worksheet, actor/location labels, authority checks, and no-secret/no-deployment-evidence boundary.
- `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/01-read-only-inventory/lesson.yaml`: installed-version/help, cluster/resource/access-object inventory, collision checks, and filtered-result stop conditions.
- `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/02-map-provider-authority/lesson.yaml`: exact provider HTTP surface, actor separation, candidate privilege matrix, accepted global `/vms` limitation, and installed-version proof requirements.
- `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/03-create-identity-roles-and-acls/lesson.yaml`: administrator-operated user/token/role/ACL sequence, effective user/token intersection, partial-failure reconciliation, and reverse-order rollback worksheet.
- `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/04-add-named-profile/lesson.yaml`: additive TOML profile entry, external hidden secret population, TLS verification, and profile preservation.
- `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/05-run-get-only-health/lesson.yaml`: explicit profile health and provider-aware validation, four GETs, and fail-closed diagnosis without privilege broadening.
- `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/06-authorize-scratch-lifecycle/lesson.yaml`: separately approved isolated-state start/destroy protocol, protected ownership-state backup, lifecycle call order, and uncertainty handling.
- `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/07-reconcile-and-rollback/lesson.yaml`: positive cleanup, independent administrator confirmation, retain/revoke choice, reverse-order rollback, and draft/certification boundary.
- `tests/test_provider_bootstrap_course.py`: loads real curriculum and locks lesson order, NONE policy, answer behavior, endpoint/matrix/profile/safety content, absence from certification registry, and placeholder/deployment-data safeguards.
- `tests/test_cli.py`: real source-tree start/save/resume regression with tripwires for every forbidden dependency.
- `tests/test_packaging.py`: extends the existing single wheel build/install smoke script to load and exercise the packaged course.
- `src/learnlab/collections/proxmox/courses/nixos-template/lessons/06-configure-provider/lesson.yaml`: replaces the generic account-setup handoff with the optional bootstrap-course link while preserving direct expert setup and NONE scope.
- `tests/test_nixos_template_course.py`: locks the optional, non-prerequisite cross-link and unchanged no-provider boundary.
- `tests/test_course_authoring_docs.py`: locks the five-part NONE-scope bootstrap exception without weakening the general side-effect prohibitions.
- `docs/LearnLab-Course-Authoring-Guide.md`: defines the narrow learner-operated bootstrap exception for NONE scope.
- `README.md`: distinguishes provider bootstrap, template bootstrap, and the provider-backed administration course.
- `docs/course-validation/2026-09-11-proxmox-provider-bootstrap.md`: records exact final digest, offline evidence, unchanged warnings, and the unexecuted live protocol.

---

### Task 1: Safety worksheet and read-only inventory

**Files:**
- Create: `tests/test_provider_bootstrap_course.py`
- Create: `src/learnlab/collections/proxmox/courses/provider-bootstrap/course.yaml`
- Create: `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/00-safety-and-private-worksheet/lesson.yaml`
- Create: `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/01-read-only-inventory/lesson.yaml`

**Interfaces:**
- Consumes: `CurriculumCatalog(ROOT).load_course("proxmox/provider-bootstrap")`, `Course.effective_environment(lesson)`, and `VerificationType`.
- Produces: `load_course()`, `lesson_text(lesson_id)`, and `all_course_text()` test helpers reused by Tasks 2–4; a valid two-lesson NONE-scope course that later tasks extend to eight lessons.

- [ ] **Step 1: Record the comparison base and re-read the approved safety, worksheet, and inventory contract**

Run:

```bash
git rev-parse HEAD
sed -n '169,214p' docs/superpowers/specs/2026-09-11-proxmox-provider-bootstrap-design.md
```

Expected: record the exact 40-character commit as `IMPLEMENTATION_BASE` in the task ledger; confirm the exact first two lesson IDs, private worksheet contents, read-only inventory, execution-location labels, expected outcomes, resume reinspection, and fail-closed stop conditions.

- [ ] **Step 2: Write failing structural and contract tests**

Create the test helpers and assertions below. Use complete exact path fragments, not generic words alone:

```python
from pathlib import Path

from learnlab.course_certification import CourseMaturity
from learnlab.curriculum import CurriculumCatalog, EnvironmentScope, VerificationType

ROOT = Path(__file__).parents[1] / "src/learnlab/collections"
COURSE_PATH = "proxmox/provider-bootstrap"


def load_course():
    return CurriculumCatalog(ROOT).load_course(COURSE_PATH)


def lesson_text(lesson_id: str) -> str:
    lesson = next(item for item in load_course().lessons if item.id == lesson_id)
    return "\n".join(step.instructions for step in lesson.steps)


def all_course_text() -> str:
    return "\n".join(lesson_text(lesson.id) for lesson in load_course().lessons)


def test_initial_bootstrap_slice_is_draft_and_has_no_managed_environment():
    course = load_course()
    assert course.maturity is CourseMaturity.DRAFT
    assert [lesson.id for lesson in course.lessons] == [
        "safety-and-private-worksheet",
        "read-only-inventory",
    ]
    for lesson in course.lessons:
        policy = course.effective_environment(lesson)
        assert policy.scope is EnvironmentScope.NONE
        assert policy.provider_capability is None
        assert policy.guest_capabilities == ()
        assert all(
            check.type in {
                VerificationType.TEXT_EVIDENCE,
                VerificationType.MANUAL_CONFIRMATION,
            }
            for step in lesson.steps
            for check in step.verifications
        )


def test_inventory_is_private_read_only_and_fails_closed():
    text = lesson_text("read-only-inventory")
    for fragment in (
        "installed PVE version", "command help", "source template",
        "storage", "network", "users", "tokens", "roles", "ACLs",
        "collision", "403", "filtered", "stop",
    ):
        assert fragment in text
```

- [ ] **Step 3: Run the new test and observe the missing-course failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py -q
```

Expected: FAIL because `proxmox/provider-bootstrap/course.yaml` does not exist.

- [ ] **Step 4: Author the two complete introductory lessons**

Create `course.yaml` with this exact initial order:

```yaml
id: provider-bootstrap
title: Bootstrap a Proxmox Provider for LearnLab
environment:
  scope: none
lessons:
  - safety-and-private-worksheet
  - read-only-inventory
```

Author lesson 00 with the step IDs `establish-boundary`, `prepare-private-worksheet`, and `confirm-resume-rules`. Every operator instruction must start with either `Controller:` or `Proxmox node:`; require existing administrator authority, an owner-only private worksheet, explicit administrator/runtime/scratch boundaries, full identity rather than VMID/name alone, and resume reinspection after any interruption. Its `course-operation-boundary` text check accepts `learner-operated`, and its manual confirmation must record no command output or deployment value.

Author lesson 01 with the step IDs `inspect-installed-version`, `inventory-resources`, and `inventory-access-objects`. Require installed command help and privilege inspection, then read-only cluster/node/source-template/storage/network inventory and current user/token/role/ACL inventory. Check proposed names and scratch targets for collisions and confirm the source template by multiple identity attributes. Every failed query, 403, incomplete or filtered list, duplicate identity, or unexpected existing object is a stop condition, never permission to create over or delete it.

```text
The worksheet remains outside the repository and contains no token secret, password, private key, authorization header, or raw secret-manager output. No worksheet value or inventory output is pasted into LearnLab.
```

Add the `inventory-mode` exact-answer check accepting `read-only inventory` and a separate manual confirmation labeled as self-attestation.

- [ ] **Step 5: Run the focused tests and offline validator**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py -q
.venv/bin/learnlab validate proxmox/provider-bootstrap
```

Expected: tests PASS; validation passes with no findings and performs no provider/network work.

- [ ] **Step 6: Commit the introductory slice**

```bash
git add tests/test_provider_bootstrap_course.py src/learnlab/collections/proxmox/courses/provider-bootstrap
git commit -m "feat: teach provider bootstrap contract"
```

---

### Task 2: Least-privilege design and administrator-operated ACL setup

**Files:**
- Modify: `tests/test_provider_bootstrap_course.py`
- Modify: `src/learnlab/collections/proxmox/courses/provider-bootstrap/course.yaml`
- Create: `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/02-map-provider-authority/lesson.yaml`
- Create: `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/03-create-identity-roles-and-acls/lesson.yaml`

**Interfaces:**
- Consumes: Task 1 test helpers and the endpoint matrix in the approved spec.
- Produces: four ordered lessons and complete actor/permission/ACL/rollback guidance consumed by the profile and live-protocol lessons.

- [ ] **Step 1: Add failing tests for actor separation and fail-closed permissions**

Extend the expected order through `create-identity-roles-and-acls`, then add assertions with exact safety phrases:

```python
def test_permission_design_preserves_global_vms_limit_and_actor_separation():
    text = lesson_text("map-provider-authority")
    for fragment in (
        "installed-version/live-confirmation-required",
        "bootstrap administrator",
        "template builder",
        "validation-only caller",
        "runtime user",
        "privilege-separated token",
        "intersection",
        "propagated ACL at /vms",
        "cluster-global VMID",
        "no pool",
        "broader",
        "source template",
        "target VM",
        "storage",
        "network",
        "node",
        "guest agent",
        "VM.GuestAgent.FileRead",
        "VM.GuestAgent.FileWrite",
        "VM.GuestAgent.FileSystemMgmt",
        "VM.GuestAgent.Unrestricted",
    ):
        assert fragment in text


def test_acl_setup_forbids_broad_fallback_and_requires_reconciliation():
    text = lesson_text("create-identity-roles-and-acls")
    for fragment in (
        "privsep=1",
        "PVEAuditor",
        "PVEVMAdmin",
        "Administrator",
        "Datastore.Allocate",
        "Datastore.AllocateSpace",
        "Datastore.AllocateTemplate",
        "Datastore.Audit",
        "403",
        "filtered",
        "propagate",
        "effective permissions",
        "reverse order",
    ):
        assert fragment in text
    assert "Do not assign Administrator" in text
    assert "Do not add Datastore.Allocate" in text


def test_provider_authority_names_every_current_request_and_limit():
    text = lesson_text("map-provider-authority")
    ordered_operations = (
        "GET /version",
        "GET /nodes",
        "GET /cluster/resources?type=vm",
        "GET /nodes/{node}/qemu/{template_vmid}/config",
        "GET /cluster/nextid",
        "POST /nodes/{profile_node}/qemu/{template_vmid}/clone",
        "clone task wait: GET /nodes/{node}/tasks/{upid}/status",
        "post-clone locate: GET /cluster/resources?type=vm",
        "POST /nodes/{node}/qemu/{vmid}/status/start",
        "start task wait: GET /nodes/{node}/tasks/{upid}/status",
        "POST /nodes/{node}/qemu/{vmid}/agent/ping",
        "GET /nodes/{node}/qemu/{vmid}/agent/network-get-interfaces",
        "cleanup preflight locate: GET /cluster/resources?type=vm",
        "POST /nodes/{node}/qemu/{vmid}/status/stop",
        "stop task wait: GET /nodes/{node}/tasks/{upid}/status",
        "DELETE /nodes/{node}/qemu/{vmid}",
        "delete task wait: GET /nodes/{node}/tasks/{upid}/status",
        "final locate: GET /cluster/resources?type=vm",
    )
    positions = [text.index(fragment) for fragment in ordered_operations]
    assert positions == sorted(positions)
    for fragment in (
        "newid",
        "generated name",
        "full=1",
        "configured storage",
        "semantically read-only",
        "does not compare the returned node",
        "no pool",
    ):
        assert fragment in text

    for check_id in (
        "api-reachable",
        "template-visible",
        "vm-running",
        "guest-agent-ready",
    ):
        assert check_id in text

    for privilege in (
        "Sys.Audit", "VM.Audit", "VM.Clone", "VM.Allocate",
        "Datastore.AllocateSpace", "Datastore.Audit", "SDN.Use",
        "SDN.Audit", "VM.PowerMgmt", "VM.GuestAgent.Audit",
    ):
        matching_rows = [line for line in text.splitlines() if privilege in line]
        assert matching_rows, privilege
        assert all(
            "installed-version/live-confirmation-required" in line
            for line in matching_rows
        ), privilege
```

- [ ] **Step 2: Run the focused tests and observe missing-lesson failures**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py -q
```

Expected: FAIL because lessons 02 and 03 are not yet present.

- [ ] **Step 3: Author the permission-design lesson**

Before authoring, re-read `src/learnlab/providers/proxmox.py` and `src/learnlab/lifecycle.py`; if their request surface differs from the approved spec, stop and revise the documents before changing curriculum. Append `map-provider-authority` to `course.yaml`. Give lesson 02 the step IDs `map-health-surface`, `separate-actors`, `map-resource-scopes`, and `accept-current-vms-limit`.

The resource matrix must separately name API root/version, node visibility, source template clone/config, propagated `/vms` allocation and target lifecycle, target datastore full-copy use, configured bridge use, task visibility, and guest-agent query. Include the candidate names `Sys.Audit`, `VM.Audit`, `VM.Clone`, `VM.Allocate`, `Datastore.AllocateSpace`, `Datastore.Audit`, `SDN.Use`, `SDN.Audit`, `VM.PowerMgmt`, and likely `VM.GuestAgent.Audit`, while placing `installed-version/live-confirmation-required` in every row containing a candidate privilege. Keep next-ID and own-task/node audit authority explicitly unproven. Prohibit guest-agent file read/write, filesystem management, unrestricted, console, and monitor rights without evidence. Do not state that a built-in role proves least privilege. Explain that the global next-ID request and pool-less clone make propagated `/vms` authority necessary for the current adapter and broader than a pool-scoped design. Require a dedicated non-human user plus separated token and effective-permission intersection. Distinguish all four exact check IDs, state that `vm-running` does not compare the returned node, and identify POST agent ping as semantically read-only. Present the operations in code order with the exact unique labels used by the test: clone task wait, post-clone locate, start task wait, cleanup preflight locate, stop task wait, delete task wait, and final locate. Include clone parameters `newid`, generated name, `full=1`, and configured storage. The `permission-proof` exact-answer check accepts `installed and live`.

- [ ] **Step 4: Author the administrator-operated identity and ACL lesson**

Append `create-identity-roles-and-acls` to `course.yaml`. Give lesson 03 the step IDs `inventory-before-change`, `create-dedicated-identities`, `create-custom-roles`, `apply-acls-one-scope-at-a-time`, and `reconcile-effective-authority`.

Use parameterized command shapes such as:

```sh
# Proxmox node: inspect installed syntax; do not copy output into LearnLab
pveum help
pveum role list --output-format json
pveum acl list --output-format json
```

Do not ship a finished cluster-specific mutation command. Mark `User.Modify` and `Permissions.Modify` as installed-version candidates reserved for the already-authorized bootstrap administrator, never the runtime identity. Require the learner to record privately each intended object, path, role, propagation flag, exact before state, expected result, and reverse action; verify absence with authorized inventory before create; capture the one-time token secret only into an approved external hidden mechanism; verify `privsep=1`; add user and token ACLs one resource scope at a time; and compare effective user and token permissions separately. The `token-authority` exact-answer check accepts `intersection`.

Include the PVE 9.2.11 development observation only as non-portable context: the built-in `PVEDatastoreAdmin` contained `Datastore.Allocate`, so the live discovery used a custom role containing only `Datastore.AllocateSpace`, `Datastore.AllocateTemplate`, and `Datastore.Audit` for human template-builder storage. State that the runtime clone-storage role is a separate installed/live-confirmed surface. A 403, extra inheritance, missing privilege, filtered result, or partial mutation stops the sequence for exact reconciliation; it never triggers `Administrator`, `PVEAdmin`, broad `PVEVMAdmin`, an unseparated token, or `Datastore.Allocate` fallback.

- [ ] **Step 5: Run focused tests and validation**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py -q
.venv/bin/learnlab validate proxmox/provider-bootstrap
```

Expected: PASS with no course findings.

- [ ] **Step 6: Commit the permissions slice**

```bash
git add tests/test_provider_bootstrap_course.py src/learnlab/collections/proxmox/courses/provider-bootstrap
git commit -m "feat: teach scoped Proxmox provider access"
```

---

### Task 3: Additive profile entry and GET-only validation

**Files:**
- Modify: `tests/test_provider_bootstrap_course.py`
- Modify: `src/learnlab/collections/proxmox/courses/provider-bootstrap/course.yaml`
- Create: `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/04-add-named-profile/lesson.yaml`
- Create: `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/05-run-get-only-health/lesson.yaml`

**Interfaces:**
- Consumes: current `ProxmoxProfile` fields, `learnlab provider test PROFILE`, `learnlab validate COURSE --provider PROFILE`, and Task 2's four-GET health contract.
- Produces: six ordered lessons and a generic, secret-free profile/health handoff for the later isolated lifecycle protocol.

- [ ] **Step 1: Add failing tests for profile preservation, secret handling, and health limits**

Extend the expected order through `run-get-only-health`, then add:

```python
def test_named_profile_is_additive_secret_free_and_tls_verified():
    text = lesson_text("add-named-profile")
    for field in (
        "type", "api_url", "token_id", "token_secret_env", "template_vmid",
        "template_name", "node", "storage", "network", "ssh_user",
        "ssh_identity_file", "tls_verify", "template_capabilities",
    ):
        assert field in text
    for fragment in (
        "preserve every existing provider",
        "preserve existing default_provider",
        "external hidden shell read",
        "LearnLab resolves only the environment variable",
        "tls_verify = true",
        "shell tracing",
        "unset",
    ):
        assert fragment in text


def test_health_lesson_distinguishes_observation_from_mutation_proof():
    text = lesson_text("run-get-only-health")
    assert 'learnlab provider test "$PROFILE"' in text
    assert 'learnlab validate "$COURSE" --provider "$PROFILE"' in text
    for fragment in (
        "four GET requests", "necessary but not sufficient", "storage",
        "network", "inferred", "403", "do not broaden", "does not certify",
    ):
        assert fragment in text
```

- [ ] **Step 2: Run the tests and observe missing-lesson failures**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py -q
```

Expected: FAIL because lessons 04 and 05 do not exist.

- [ ] **Step 3: Author the additive named-profile lesson**

Append `add-named-profile` to `course.yaml`. Give lesson 04 the step IDs `back-up-config`, `add-unused-profile`, `supply-secret-externally`, and `inspect-without-copying`.

Show a generic table using visibly synthetic metavariables, for example:

```toml
[providers."CHOSEN_PROFILE"]
type = "proxmox"
api_url = "HTTPS_API_ORIGIN"
token_id = "DEDICATED_USER_AND_TOKEN_ID"
token_secret_env = "UNIQUE_SECRET_VARIABLE_NAME"
template_vmid = POSITIVE_TEMPLATE_ID
template_name = "EXACT_TEMPLATE_NAME"
node = "TEMPLATE_NODE"
storage = "TARGET_STORAGE"
network = "TARGET_BRIDGE"
ssh_user = "GUEST_LEARNER_USER"
ssh_identity_file = "CONTROLLER_PRIVATE_KEY_PATH"
tls_verify = true
template_capabilities = ["VERIFIED_CAPABILITY_ID"]
```

Explain every field. Require an owner-only config backup, unused table name, preservation of all providers/defaults, and explicit profile selection. Only a genuinely new config with no default may receive one. State that `token_secret_env` stores only a variable name; an external hidden shell read or secret manager populates it before LearnLab starts; LearnLab has no stdin/prompt secret resolver. Forbid secrets in TOML, arguments, history, output, logs, screenshots, snapshots, progress, tests, and evidence; keep shell tracing off and unset the selected variable after use. TLS remains on and trust/hostname/clock problems are fixed rather than bypassed. The `secret-storage` exact-answer check accepts `environment-variable name`.

- [ ] **Step 4: Author the GET-only health lesson**

Append `run-get-only-health` to `course.yaml`. Give lesson 05 the step IDs `select-profile`, `run-provider-health`, `run-provider-aware-validation`, and `interpret-failures`.

Display only learner-operated command shapes:

```sh
# Controller
read -r PROFILE
learnlab provider test "$PROFILE"
read -r COURSE
learnlab validate "$COURSE" --provider "$PROFILE"
```

Name the exact four health GETs and state that storage/network matching is inferred from the template config, not queried authorization. A passing result is necessary but insufficient, proves no mutation rights, authorizes no lifecycle, and certifies no course/template/profile. A missing or denied object may be filtered. On 403 or mismatch, return to exact user/token/path permission reconciliation and do not broaden roles. Add the `health-proof` exact-answer check accepting `GET-only observation`.

- [ ] **Step 5: Run focused tests and validation**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py -q
.venv/bin/learnlab validate proxmox/provider-bootstrap
```

Expected: PASS with no findings and no external calls.

- [ ] **Step 6: Commit the profile/health slice**

```bash
git add tests/test_provider_bootstrap_course.py src/learnlab/collections/proxmox/courses/provider-bootstrap
git commit -m "feat: guide provider profile health checks"
```

---

### Task 4: Separately authorized lifecycle, positive cleanup, and rollback

**Files:**
- Modify: `tests/test_provider_bootstrap_course.py`
- Modify: `src/learnlab/collections/proxmox/courses/provider-bootstrap/course.yaml`
- Create: `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/06-authorize-scratch-lifecycle/lesson.yaml`
- Create: `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/07-reconcile-and-rollback/lesson.yaml`

**Interfaces:**
- Consumes: existing `proxmox/proxmox-admin` start/destroy CLI, XDG state-root behavior, and Tasks 1–3's private worksheet/profile/permission contracts.
- Produces: the final exact eight-lesson course and the complete documented live protocol, which remains unexecuted during implementation.

- [ ] **Step 1: Add failing final-order and lifecycle safety tests**

Replace the incremental order assertion with the final exact list and add:

```python
def test_complete_lesson_order():
    assert [lesson.id for lesson in load_course().lessons] == [
        "safety-and-private-worksheet", "read-only-inventory",
        "map-provider-authority", "create-identity-roles-and-acls",
        "add-named-profile", "run-get-only-health",
        "authorize-scratch-lifecycle", "reconcile-and-rollback",
    ]


def test_live_protocol_is_separate_isolated_and_fail_closed():
    text = lesson_text("authorize-scratch-lifecycle")
    for fragment in (
        "separate explicit authorization", "scratch profile", "isolated",
        "XDG", "empty", "proxmox/proxmox-admin", "--provider \"$PROFILE\"",
        "--include-drafts", "owner-only backup", "preserve-progress",
        "erase-progress", "filtered inventory", "uncertain", "do not retry",
    ):
        assert fragment in text


def test_cleanup_precedes_revocation_and_keeps_recovery_evidence():
    text = lesson_text("reconcile-and-rollback")
    for fragment in (
        "completed delete task", "authorized refreshed inventory",
        "attached scratch storage", "source template still present",
        "independent administrator", "protected state backup", "Retain",
        "Revoke", "token first", "reverse order", "unexpected reference",
        "course remains draft",
    ):
        assert fragment in text
```

Add the exact answer-contract test:

```python
@pytest.mark.parametrize(
    ("lesson_id", "check_id", "accepted", "rejected"),
    [
        ("safety-and-private-worksheet", "course-operation-boundary", "learner-operated", "automated"),
        ("read-only-inventory", "inventory-mode", "read-only inventory", "mutation"),
        ("map-provider-authority", "permission-proof", "installed and live", "built-in role"),
        ("create-identity-roles-and-acls", "token-authority", "intersection", "user only"),
        ("add-named-profile", "secret-storage", "environment-variable name", "secret value"),
        ("run-get-only-health", "health-proof", "GET-only observation", "lifecycle authorized"),
        ("authorize-scratch-lifecycle", "authorization-scope", "one approved scratch lifecycle", "general permission"),
        ("reconcile-and-rollback", "progress-kind", "self-attested progress", "certified"),
    ],
)
def test_knowledge_checks_execute_exact_answer_contract(
    lesson_id, check_id, accepted, rejected
):
    class AnswerPrompt:
        def __init__(self, answer):
            self.answer = answer

        def ask_text(self, prompt):
            return self.answer

    from learnlab.validation import TextEvidenceValidator, ValidationContext

    lesson = next(item for item in load_course().lessons if item.id == lesson_id)
    checks = {
        check.id: check
        for step in lesson.steps
        for check in step.verifications
        if check.type is VerificationType.TEXT_EVIDENCE
    }
    assert set(checks) == {check_id}
    for answer, expected in (
        (accepted, True), (rejected, False), ("", False), ("unrelated", False)
    ):
        result = TextEvidenceValidator().validate(
            ValidationContext(prompt=AnswerPrompt(answer)), checks[check_id]
        )
        assert result.passed is expected


def test_course_has_no_unfinished_or_live_deployment_values():
    text = all_course_text()
    for forbidden in (
        "T" + "ODO", "T" + "BD", "192.168.", "pve02", "learnlab@pve",
        "!provider", "vm-103", "local-lvm", "local-ssd",
    ):
        assert forbidden not in text
    assert not re.search(r"https?://(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?", text)
    assert not re.search(
        r"(?i)\b(?:vmid|template_vmid)\s*(?:=|:)\s*[1-9]\d{2,8}\b", text
    )
```

Add `import re` and `import pytest` at the top. The VMID detector is context-aware, so required permission modes such as `600` and `700`, HTTP status codes, and version numbers remain legal while concrete `vmid`/`template_vmid` assignments are rejected.

- [ ] **Step 2: Run focused tests and observe missing-lesson failures**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py -q
```

Expected: FAIL because the two final lessons are absent.

- [ ] **Step 3: Author the separate scratch-lifecycle authorization lesson**

Append `authorize-scratch-lifecycle` to `course.yaml`. Give lesson 06 the step IDs `request-live-authorization`, `prepare-isolated-state`, `run-one-managed-environment`, and `back-up-before-destroy`.

The authorization must name privately the scratch profile, source template, storage/network targets, time window, exactly one disposable lifecycle, cleanup obligation, and independent reconciler. Teach the learner to keep the normal configuration root unchanged while isolating only state with these exact controller commands:

```sh
# Controller: create a private isolated state root; do not change XDG_CONFIG_HOME
read -r SCRATCH_STATE_PARENT
install -d -m 700 "$SCRATCH_STATE_PARENT"
export XDG_STATE_HOME="$SCRATCH_STATE_PARENT/state"
install -d -m 700 "$XDG_STATE_HOME"
find "$XDG_STATE_HOME" -mindepth 1 -maxdepth 1 -print -quit
```

`SCRATCH_STATE_PARENT` is an unused private directory chosen outside the repository. Expected: the final `find` prints nothing. If it prints anything, stop and choose a different empty directory; never erase an existing state root to make this check pass. Confirm the normal config still supplies the explicitly selected scratch profile, then run:

```sh
# Controller: only inside the separately approved window
learnlab start proxmox/proxmox-admin --provider "$PROFILE" --include-drafts
```

Require enough ordinary first-lesson completion to observe the managed environment and guest path, then a clean exit. Before normal `learnlab destroy`, require an owner-only backup of the isolated lifecycle ownership state and retention of the private worksheet:

```sh
# Controller: after start exits and before destroy
install -d -m 700 "$SCRATCH_STATE_PARENT/backup"
install -m 600 "$XDG_STATE_HOME/learnlab/learnlab.db" \
  "$SCRATCH_STATE_PARENT/backup/learnlab.db.pre-destroy"
```

Expected: both database paths are owner-only and the backup remains outside the repository. If the source database is absent or either permission/identity check is ambiguous, stop before destroy. Present both normal destroy choices, `--preserve-progress` and `--erase-progress`, without choosing for the learner. After the learner independently reconciles cleanup, unset `XDG_STATE_HOME`; retain or remove the isolated directory only according to the separately approved evidence-retention decision. Make clear the course displays but never executes these commands.

List the expected lifecycle call order exactly. Add the `authorization-scope` exact-answer check accepting `one approved scratch lifecycle`. Require safe denial-boundary evidence, where the administrator can obtain it without uncertain state, that `Datastore.Allocate`, `VM.GuestAgent.FileRead`, `VM.GuestAgent.FileWrite`, `VM.GuestAgent.FileSystemMgmt`, and `VM.GuestAgent.Unrestricted` remain absent and unnecessary; an ambiguous denial test blocks acceptance rather than inviting broader rights. State that ACL-filtered inventory may omit a real VM and the current adapter may then remove local ownership state, so the protected pre-destroy backup and worksheet remain authoritative recovery evidence. A collision, 403, timeout, malformed response, transport loss, uncertain clone/delete, or filtered inventory blocks retry, state cleanup, and ACL revocation until administrator reconciliation.

- [ ] **Step 4: Author cleanup, retention, revocation, and certification boundaries**

Append `reconcile-and-rollback` to `course.yaml`. Give lesson 07 the step IDs `prove-positive-cleanup`, `obtain-independent-confirmation`, `choose-retain-or-revoke`, and `separate-progress-from-certification`.

Require the generated name/VMID to match the protected ownership record and private worksheet, a completed delete task, no active/unresolved task, authorized refreshed inventory proving the exact managed identity absent, expected scratch storage absent, and source template present. Retain completed task history as audit evidence; do not describe it as a residual resource. A 404/missing row alone is insufficient. An administrator other than the runtime token confirms no scratch VM, unresolved task, or residual storage remains before permissions are changed.

For `Retain`, keep the profile, dedicated user/token, roles, ACLs, and external secret mechanism under periodic review. For `Revoke`, disable/delete the token first, remove only bootstrap-created ACLs, remove the dedicated user only when unused/unowned, and remove custom roles only when unreferenced; re-inventory after every reverse-order action. Unexpected references or filtered/denied inventory stop rollback. End with the `progress-kind` exact-answer check accepting `self-attested progress`, and state that the course remains draft until a separately authorized exact-digest live acceptance is recorded.

- [ ] **Step 5: Run the complete focused content gate**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py -q
.venv/bin/learnlab validate proxmox/provider-bootstrap
```

Expected: PASS; exact eight-lesson order; no validation findings.

- [ ] **Step 6: Commit the lifecycle/cleanup slice**

```bash
git add tests/test_provider_bootstrap_course.py src/learnlab/collections/proxmox/courses/provider-bootstrap
git commit -m "feat: document provider lifecycle acceptance"
```

---

### Task 5: Integrate the optional NixOS handoff and authoring documentation

**Files:**
- Modify: `tests/test_nixos_template_course.py`
- Modify: `tests/test_course_authoring_docs.py`
- Modify: `src/learnlab/collections/proxmox/courses/nixos-template/lessons/06-configure-provider/lesson.yaml`
- Modify: `docs/LearnLab-Course-Authoring-Guide.md`
- Modify: `README.md`
- Modify: `tests/test_provider_bootstrap_course.py`

**Interfaces:**
- Consumes: the finished `proxmox/provider-bootstrap` course path and existing NixOS `configure-provider` lesson.
- Produces: an optional cross-link, a narrow authoring rule for learner-operated NONE courses, and user-facing course-selection guidance without changing runtime behavior.

- [ ] **Step 1: Add failing integration/documentation tests**

Add to `tests/test_nixos_template_course.py`:

```python
def test_provider_bootstrap_cross_link_is_optional_and_keeps_none_scope():
    text = lesson_text("configure-provider")
    assert "proxmox/provider-bootstrap" in text
    assert "optional" in text.lower()
    assert "direct advanced setup" in text.lower()
    assert "not a prerequisite" in text.lower()
    policy = load_course().effective_environment(
        next(item for item in load_course().lessons if item.id == "configure-provider")
    )
    assert policy.scope is EnvironmentScope.NONE
    assert policy.provider_capability is None
```

Add the exact authoring-guide regression beside the existing documentation tests:

```python
def test_none_scope_bootstrap_exception_remains_narrow() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    section = guide[guide.index("## 6. Environments") : guide.index("## 7.")]
    for fragment in (
        "learner-operated bootstrap",
        "no LearnLab dependency or verification",
        "execution location",
        "explicit checkpoint",
        "identity preflight",
        "expected result",
        "rollback",
        "fail closed",
        "non-secret self-attestation",
        "never command output or deployment data",
        "not provider or infrastructure validation",
        "remote-command",
        "provider-check",
    ):
        assert fragment.lower() in section.lower()
```

Add the README regression to `tests/test_provider_bootstrap_course.py`:

```python
def test_readme_distinguishes_provider_and_template_bootstrap_paths():
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    for fragment in (
        "proxmox/provider-bootstrap",
        "proxmox/nixos-template",
        "proxmox/proxmox-admin",
        "optional",
        "provider-backed",
        "learnlab start proxmox/provider-bootstrap --include-drafts",
        "self-attestation",
        "not live certification",
    ):
        assert fragment in readme
```

- [ ] **Step 2: Run the documentation-focused tests and observe failures**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py tests/test_nixos_template_course.py tests/test_course_authoring_docs.py -q
```

Expected: FAIL because the cross-link, authoring exception, and README entry are absent.

- [ ] **Step 3: Replace the NixOS generic account handoff with two explicit options**

In `configure-provider`, keep the current direct setup content for advanced operators, but lead account/ACL setup with:

```text
Optional guided path: leave this NONE-scope course and start
`learnlab start proxmox/provider-bootstrap --include-drafts` on the controller.
It is guidance, not a prerequisite, and it does not make provider calls. An
authorized advanced operator may instead perform the same scoped setup directly.
```

Do not add a course requirement, provider capability, provider verification, or automatic transition. Preserve all NixOS profile fields, compatibility checks, clone reconciliation, and self-attestation/certification boundaries.

- [ ] **Step 4: Add the narrow authoring-guide exception**

Change the `none` table row from purely conceptual to conceptual or tightly controlled learner-operated bootstrap guidance. Immediately below the NONE constraints, add the five mandatory conditions verbatim in substance:

1. no LearnLab dependency or verification performs the operation;
2. every operator command names its shell/location and has an explicit checkpoint;
3. mutations include identity preflight, expected result, rollback, and fail-closed handling;
4. LearnLab records only non-secret self-attestation or conceptual answers, never command output/deployment data; and
5. offline completion is not provider/infrastructure validation.

Retain the bans on `remote-command`, `provider-check`, capabilities, automatic side effects, and mid-course LearnLab permission mutation.

- [ ] **Step 5: Update README course selection**

Add a compact section distinguishing:

```text
proxmox/provider-bootstrap  optional NONE-scope guidance for creating a named profile
proxmox/nixos-template      learner-operated template construction, also NONE scope
proxmox/proxmox-admin       provider-backed disposable VM course after a working profile exists
```

Show the draft opt-in command and state that completion/self-attestation is neither provider validation nor live certification.

- [ ] **Step 6: Run focused tests, both course validators, and digest checks**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py tests/test_nixos_template_course.py tests/test_course_authoring_docs.py -q
.venv/bin/learnlab validate proxmox/provider-bootstrap
.venv/bin/learnlab validate proxmox/nixos-template
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from learnlab.course_certification import course_digest
for path in ("provider-bootstrap", "nixos-template"):
    root = Path("src/learnlab/collections/proxmox/courses") / path
    print(path, course_digest(root))
PY
```

Expected: focused tests and validators PASS; both digests print; both courses load as `draft` because no matching certification record exists.

- [ ] **Step 7: Commit the documentation integration**

```bash
git add README.md docs/LearnLab-Course-Authoring-Guide.md tests/test_provider_bootstrap_course.py tests/test_nixos_template_course.py tests/test_course_authoring_docs.py src/learnlab/collections/proxmox/courses/nixos-template/lessons/06-configure-provider/lesson.yaml
git commit -m "docs: link provider bootstrap guidance"
```

---

### Task 6: Add post-feature source and installed-wheel regression proof

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `tests/test_packaging.py`

**Interfaces:**
- Consumes: the final course, `StateStore`, `CliRunner`, `CourseMaturity`, existing NixOS start/resume test patterns, and the single wheel build/install smoke test.
- Produces: source-tree and installed-package characterization evidence that draft gating, start/save/resume, self-attestation, and forbidden dependency isolation work end to end. This task adds no production behavior and is explicitly verification-only rather than a RED/GREEN implementation cycle.

- [ ] **Step 1: Add the source CLI isolation characterization test**

Clone the existing NixOS bootstrap pattern but target the new course and patch every forbidden dependency:

```python
def test_provider_bootstrap_start_save_resume_never_touches_external_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli
    from learnlab.curriculum import CurriculumCatalog

    collections = Path(__file__).parents[1] / "src/learnlab/collections"
    catalog = CurriculumCatalog(collections)
    registry_before = (collections / "certifications.yaml").read_bytes()
    store = StateStore(tmp_xdg / "provider-bootstrap-state" / "learnlab.db")

    def forbidden(*args, **kwargs):
        raise AssertionError("provider bootstrap touched an external dependency")

    monkeypatch.setattr(cli, "catalog_factory", lambda: catalog)
    monkeypatch.setattr(cli, "state_store_factory", lambda: store)
    monkeypatch.setattr(cli, "state_root", lambda: tmp_xdg / "provider-bootstrap-state")
    for name in (
        "load_settings", "load_requested_profiles", "resolve_token_secret",
        "provider_factory", "SshExecutor",
    ):
        monkeypatch.setattr(cli, name, forbidden)
    monkeypatch.setattr("learnlab.providers.proxmox.httpx.Client", forbidden)

    gated = CliRunner().invoke(cli.app, ["start", "proxmox/provider-bootstrap"])
    assert gated.exit_code == 2
    assert "--include-drafts" in gated.output

    started = CliRunner().invoke(
        cli.app,
        ["start", "proxmox/provider-bootstrap", "--include-drafts"],
        input="1\n\nlearner-operated\n\ny\nq\n",
    )
    assert started.exit_code == 0, started.output
    assert "Environment policy: none" in started.output
    assert "Progress saved." in started.output
    step_path = (
        "proxmox", "provider-bootstrap", "safety-and-private-worksheet",
        "prepare-private-worksheet",
    )
    [saved] = store.verification_records(step_path)
    assert saved.self_attested is True
    assert saved.evidence is None

    resumed = CliRunner().invoke(
        cli.app,
        ["resume", "proxmox/provider-bootstrap"],
        input="1\n\nq\n",
    )
    assert resumed.exit_code == 0, resumed.output
    assert "[in progress]" in resumed.output
    assert "prepare-private-worksheet" not in resumed.output
    assert store.verification_records(step_path) == [saved]
    assert catalog.load_course("proxmox/provider-bootstrap").maturity is CourseMaturity.DRAFT
    assert (collections / "certifications.yaml").read_bytes() == registry_before
```

The first lesson must keep the authored text-check/manual-confirmation order and the fixed verification IDs used by this transcript; do not weaken the test by selecting a different lesson.

- [ ] **Step 2: Run the source characterization test**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_provider_bootstrap_start_save_resume_never_touches_external_dependencies -q
```

Expected: PASS on the first run. A failure is a defect in the completed course or this exact transcript; diagnose it before proceeding and do not claim a TDD RED phase for this post-feature regression test.

- [ ] **Step 3: Verify the source test covers every forbidden dependency**

Confirm the test contains the explicit `learnlab.providers.proxmox.httpx.Client` tripwire shown above in addition to the five CLI dependencies, the exact `prepare-private-worksheet` provenance assertions, resume skip, and unchanged registry bytes. If any is absent, add that exact assertion and rerun Step 2.

- [ ] **Step 4: Extend the existing wheel smoke script without adding another build**

After wheel extraction, add these exact assertions without adding a second build:

```python
provider_prefix = "learnlab/collections/proxmox/courses/provider-bootstrap/"
assert provider_prefix + "course.yaml" in names
assert len(
    [
        name
        for name in names
        if name.startswith(provider_prefix + "lessons/")
        and name.endswith("/lesson.yaml")
    ]
) == 8
```

Immediately after the installed NixOS smoke block, add this provider-bootstrap block inside the existing embedded Python program:

```python
path = 'proxmox/provider-bootstrap'
course = catalog.load_course(path)
assert course.maturity is CourseMaturity.DRAFT
assert [lesson.id for lesson in course.lessons] == [
    'safety-and-private-worksheet', 'read-only-inventory',
    'map-provider-authority', 'create-identity-roles-and-acls',
    'add-named-profile', 'run-get-only-health',
    'authorize-scratch-lifecycle', 'reconcile-and-rollback',
]
for lesson in course.lessons:
    policy = course.effective_environment(lesson)
    assert policy.scope is EnvironmentScope.NONE
    assert policy.provider_capability is None
    assert policy.guest_capabilities == ()
    assert all(check.type in (VerificationType.TEXT_EVIDENCE,
                             VerificationType.MANUAL_CONFIRMATION)
               for step in lesson.steps for check in step.verifications)
provider_store = StateStore(Path('provider-bootstrap-state/learnlab.db'))
def provider_forbidden(*args, **kwargs):
    raise AssertionError('provider bootstrap accessed an external dependency')
with (
    patch.object(cli, 'state_store_factory', return_value=provider_store),
    patch.object(cli, 'state_root', return_value=Path('provider-bootstrap-state')),
    patch.object(cli, 'load_settings', side_effect=provider_forbidden),
    patch.object(cli, 'load_requested_profiles', side_effect=provider_forbidden),
    patch.object(cli, 'resolve_token_secret', side_effect=provider_forbidden),
    patch.object(cli, 'provider_factory', side_effect=provider_forbidden),
    patch.object(cli, 'SshExecutor', side_effect=provider_forbidden),
    patch('learnlab.providers.proxmox.httpx.Client', side_effect=provider_forbidden),
):
    gated = CliRunner().invoke(cli.app, ['start', path])
    assert gated.exit_code == 2, gated.output
    assert '--include-drafts' in gated.output
    started = CliRunner().invoke(
        cli.app, ['start', path, '--include-drafts'],
        input='1\n\nlearner-operated\n\ny\nq\n',
    )
    assert started.exit_code == 0, started.output
    step_path = ('proxmox', 'provider-bootstrap',
                 'safety-and-private-worksheet', 'prepare-private-worksheet')
    [saved] = provider_store.verification_records(step_path)
    assert saved.self_attested and saved.evidence is None
    resumed = CliRunner().invoke(
        cli.app, ['resume', path], input='1\n\nq\n'
    )
    assert resumed.exit_code == 0, resumed.output
    assert 'prepare-private-worksheet' not in resumed.output
    assert provider_store.verification_records(step_path) == [saved]
assert catalog.load_course(path).maturity is CourseMaturity.DRAFT
assert root.joinpath('certifications.yaml').read_text().strip() == 'certifications: []'
print(path + ': none; draft; start/save/resume; self-attested')
```

The embedded program already imports `patch` from `unittest.mock`; keep that import and the existing single wheel build/install. Append this exact line to the outer `pending_smoke.stdout.splitlines()` expectation:

```text
proxmox/provider-bootstrap: none; draft; start/save/resume; self-attested
```

- [ ] **Step 5: Run focused source and packaging tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_provider_bootstrap_start_save_resume_never_touches_external_dependencies -q
.venv/bin/python -m pytest tests/test_packaging.py::test_built_wheel_installs_with_curriculum_resources -q
```

Expected: both PASS; packaging builds exactly one wheel during its one invocation.

- [ ] **Step 6: Commit the runtime/packaging proof**

```bash
git add tests/test_cli.py tests/test_packaging.py
git commit -m "test: prove provider bootstrap isolation"
```

---

### Task 7: Record offline evidence and run the final review gates

**Files:**
- Create: `docs/course-validation/2026-09-11-proxmox-provider-bootstrap.md`
- Modify only if a review finds an in-scope defect: files listed in Tasks 1–6

**Interfaces:**
- Consumes: final repository content, `course_digest()`, focused tests, full non-live suite, validators, Ruff, mypy, and independent reviews.
- Produces: an exact-digest offline acceptance record that explicitly leaves live evidence unperformed and the course draft.

- [ ] **Step 1: Add a failing digest-bound report test**

Add to `tests/test_provider_bootstrap_course.py`:

```python
def test_offline_report_keeps_live_protocol_pending():
    from learnlab.course_certification import course_digest

    report = (
        Path(__file__).parents[1]
        / "docs/course-validation/2026-09-11-proxmox-provider-bootstrap.md"
    ).read_text(encoding="utf-8")
    for fragment in (
        "Status: **draft",
        "offline gate",
        "live acceptance not performed",
        "exact course digest",
        "installed-version/live-confirmation-required",
        "propagated `/vms`",
        "independent administrator",
        "no certification-registry entry",
    ):
        assert fragment.lower() in report.lower()
    [reported_digest] = re.findall(r"(?m)^`([0-9a-f]{64})`$", report)
    course_root = ROOT / "proxmox/courses/provider-bootstrap"
    assert reported_digest == course_digest(course_root)
    assert re.search(r"(?m)^Tested content revision: `[0-9a-f]{40}`$", report)
```

- [ ] **Step 2: Run the report test and observe the missing-file failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py::test_offline_report_keeps_live_protocol_pending -q
```

Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 3: Run pre-report focused gates and whole-feature reviews**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py tests/test_nixos_template_course.py tests/test_course_authoring_docs.py tests/test_cli.py tests/test_packaging.py -q -k 'not offline_report_keeps_live_protocol_pending'
.venv/bin/learnlab validate proxmox/provider-bootstrap
.venv/bin/learnlab validate proxmox/nixos-template
.venv/bin/learnlab validate --format json
```

Expected: focused tests pass with the deliberate missing-report test deselected; both course validators pass; catalog JSON contains only the unchanged pre-existing `proxmox/proxmox-admin` warnings.

Dispatch one independent spec-compliance reviewer over all Task 1–6 changes. Resolve only verified findings, rerun affected focused tests, and commit fixes as `fix: address provider bootstrap spec review`. Then dispatch a different code-quality reviewer, resolve verified findings, rerun affected tests, and commit fixes as `fix: address provider bootstrap quality review`. A clean review creates no empty commit.

- [ ] **Step 4: Run the complete post-review offline gate**

Run each command separately and inspect its exit status:

```bash
.venv/bin/python -m pytest -m 'not live' -q -k 'not offline_report_keeps_live_protocol_pending'
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/learnlab validate proxmox/provider-bootstrap
.venv/bin/learnlab validate proxmox/nixos-template
.venv/bin/learnlab validate --format json
git diff --check
```

Expected: all commands exit 0; pytest deselects the live test and the not-yet-created report test; the two target courses have no findings; catalog JSON contains only the unchanged known `proxmox/proxmox-admin` warnings; `git diff --check` prints nothing.

- [ ] **Step 5: Compute the final revision/digest and write the offline report**

Only after all course-content review fixes are committed, run:

```bash
git rev-parse HEAD
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from learnlab.course_certification import course_digest
root = Path("src/learnlab/collections/proxmox/courses/provider-bootstrap")
print(course_digest(root))
PY
```

Record the exact 40-character revision and lowercase 64-character digest in the report using the precise formats asserted in Step 1. Record the final commands and outputs, and include:

- eight ordered lessons, NONE scope, allowed verification types, and zero-dependency test result;
- code-derived endpoint coverage and GET-only limits;
- actor/permission separation and accepted propagated `/vms` limitation;
- PVE 9.2.11 findings only as development discovery, not portable proof;
- custom human template-builder datastore role observation excluding `Datastore.Allocate`;
- secret/deployment-data handling and isolated state-backup safeguard;
- unchanged validation warnings from `proxmox/proxmox-admin`;
- no provider/lifecycle/config/schema/certification changes;
- live protocol numbered 1–9 from the spec, clearly marked unexecuted;
- explicit statement that no certification-registry entry exists and the course remains draft.

Do not include the user's endpoint, node, storage names, usernames, token identity, VMIDs, ISO path, task output, secret-variable name, or other live deployment identifiers. If any course file changes after this point, repeat Step 4, recompute both values, and refresh the report before proceeding.

- [ ] **Step 6: Run the report test and exact-digest assertion**

Run:

```bash
.venv/bin/python -m pytest tests/test_provider_bootstrap_course.py::test_offline_report_keeps_live_protocol_pending -q
```

Expected: PASS; the report's single standalone digest equals `course_digest()` for the current course bytes and its tested revision is a 40-character commit.

- [ ] **Step 7: Check full committed history and current working changes**

Enter the exact `IMPLEMENTATION_BASE` recorded in Task 1, then run:

```bash
read -r IMPLEMENTATION_BASE
git cat-file -e "$IMPLEMENTATION_BASE^{commit}"
git diff --check "$IMPLEMENTATION_BASE"..HEAD
git diff --check
git diff --cached --check
.venv/bin/python - "$IMPLEMENTATION_BASE" <<'PY'
import subprocess
import sys

base = sys.argv[1]
allowed_files = {
    "README.md",
    "docs/LearnLab-Course-Authoring-Guide.md",
    "docs/course-validation/2026-09-11-proxmox-provider-bootstrap.md",
    "src/learnlab/collections/proxmox/courses/provider-bootstrap/course.yaml",
    "src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/00-safety-and-private-worksheet/lesson.yaml",
    "src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/01-read-only-inventory/lesson.yaml",
    "src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/02-map-provider-authority/lesson.yaml",
    "src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/03-create-identity-roles-and-acls/lesson.yaml",
    "src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/04-add-named-profile/lesson.yaml",
    "src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/05-run-get-only-health/lesson.yaml",
    "src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/06-authorize-scratch-lifecycle/lesson.yaml",
    "src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/07-reconcile-and-rollback/lesson.yaml",
    "src/learnlab/collections/proxmox/courses/nixos-template/lessons/06-configure-provider/lesson.yaml",
    "tests/test_cli.py",
    "tests/test_course_authoring_docs.py",
    "tests/test_nixos_template_course.py",
    "tests/test_packaging.py",
    "tests/test_provider_bootstrap_course.py",
}
commands = (
    ("git", "diff", "--name-only", f"{base}..HEAD"),
    ("git", "diff", "--name-only", "--cached"),
    ("git", "diff", "--name-only"),
    ("git", "ls-files", "--others", "--exclude-standard"),
)
changed = {
    line
    for command in commands
    for line in subprocess.run(
        command, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    if line
}
unexpected = sorted(
    path
    for path in changed
    if path not in allowed_files
)
assert not unexpected, f"out-of-scope changed paths: {unexpected}"
print(f"allowlist passed for {len(changed)} changed paths")
PY
```

Expected: the base commit resolves; all three whitespace checks print nothing; the script reports an allowlist pass. It examines committed base-to-HEAD changes, staged changes, unstaged changes, and untracked files together. The allowlist names the exact course manifest and eight lesson files rather than trusting a directory prefix, so an unexpected ninth curriculum file or any other out-of-scope path fails.

Run the secret/placeholder scan over the wholly new content and over only the added diff lines in every changed existing document:

```bash
rg -n "T[B]D|T[O]DO|implement lat[e]r|fill in deta[i]ls|example[.]com|192[.]168[.]|learnlab[@]|[!]provider|vm-10[3]|local-lv[m]|local-ss[d]|pve0[2]" src/learnlab/collections/proxmox/courses/provider-bootstrap docs/course-validation/2026-09-11-proxmox-provider-bootstrap.md
git diff --unified=0 "$IMPLEMENTATION_BASE"..HEAD -- README.md docs/LearnLab-Course-Authoring-Guide.md src/learnlab/collections/proxmox/courses/nixos-template/lessons/06-configure-provider/lesson.yaml | rg -n '^\+.*(T[B]D|T[O]DO|implement lat[e]r|fill in deta[i]ls|example[.]com|192[.]168[.]|learnlab[@]|[!]provider|vm-10[3]|local-lv[m]|local-ss[d]|pve0[2])'
```

Expected: neither scan prints an accidental deployment value or unfinished marker. Both `rg` commands normally exit 1 because no line matches; that no-match status is expected, while exit status 2 is a scan error that must be fixed. Investigate every printed match rather than suppressing it. Scanning only added diff lines avoids treating legitimate pre-existing README examples as new provider-bootstrap content.

- [ ] **Step 8: Review the report, then run the complete final offline gate**

Dispatch an independent reviewer for the report's accuracy, exact digest/revision, evidence claims, redaction, and explicit unexecuted-live boundary. The reviewer must not request or perform live work. Apply report-only corrections; if a correction unexpectedly touches a course file, return to Steps 3–7 and recompute the digest/revision.

Stage exactly the report and its test, then run every command separately and inspect its exit status:

```bash
git add docs/course-validation/2026-09-11-proxmox-provider-bootstrap.md tests/test_provider_bootstrap_course.py
.venv/bin/python -m pytest -m 'not live' -q
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/learnlab validate proxmox/provider-bootstrap
.venv/bin/learnlab validate proxmox/nixos-template
.venv/bin/learnlab validate --format json
git diff --check
git diff --cached --check
```

Expected: all commands exit 0; pytest includes the digest-bound report test and deselects only live tests; the two target courses have no findings; catalog JSON contains only the unchanged known `proxmox/proxmox-admin` warnings; both diff checks print nothing.

- [ ] **Step 9: Commit the offline evidence**

```bash
git add docs/course-validation/2026-09-11-proxmox-provider-bootstrap.md tests/test_provider_bootstrap_course.py
git commit -m "docs: record provider bootstrap offline gate"
```

- [ ] **Step 10: Verify committed branch state and stop before live work or publication**

Run:

```bash
read -r IMPLEMENTATION_BASE
git cat-file -e "$IMPLEMENTATION_BASE^{commit}"
git status --short
git log -10 --oneline
git diff --check "$IMPLEMENTATION_BASE"..HEAD
```

Expected: clean feature worktree, all reviewed implementation commits visible after this plan/spec history, and the committed base-to-HEAD whitespace check silent. Report exact verification results and digest. Do not perform the documented live protocol, add certification evidence, merge, push, or remove the retained branch/worktree without separate explicit authorization.
