# Pending Course Review and Certification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct and honestly certify the six pending courses, leaving any unproven course visibly draft.

**Architecture:** Store maturity and non-secret certification metadata beside canonical curriculum, exercise all content through the validation service, and gate ready status on a digest-matched live record. Course-family corrections remain separate commits so each can be reviewed independently.

**Tech Stack:** YAML curriculum, Python 3.13 validation tests, pytest, LearnLab CLI, disposable Proxmox VMs.

**Spec:** `docs/superpowers/specs/2026-09-08-pending-course-review-certification-design.md`

## Global Constraints

- Complete `2026-09-08-course-authoring-validation.md` first.
- Never run destructive live tests without explicit operator confirmation.
- Use scratch profiles and preserve uncertain state on interruption.
- Never store provider identities, addresses, or secrets in certification data.
- A course remains draft unless its exact digest passes live acceptance.
- Use an isolated worktree; do not push or merge implicitly.

---

### Task 1: Course Maturity and Certification Model

**Files:**
- Modify: `src/learnlab/curriculum.py`
- Create: `src/learnlab/course_certification.py`
- Create: `src/learnlab/collections/certifications.yaml`
- Modify: `tests/test_curriculum.py`
- Create: `tests/test_course_certification.py`

**Interfaces:**
- Produces: `CourseMaturity(DRAFT, OFFLINE_VALIDATED, LIVE_VALIDATED)`.
- Produces: `course_digest(course_dir) -> str` using sorted relative paths and bytes.
- Produces: `CertificationRegistry.status(course_path, digest) -> CourseMaturity`.

- [ ] **Step 1: Write digest and stale-certificate tests**

```python
def test_changed_curriculum_invalidates_live_certificate(tmp_course, registry):
    digest = course_digest(tmp_course)
    registry = registry.with_live_record("demo/admin", digest)
    assert registry.status("demo/admin", digest) is CourseMaturity.LIVE_VALIDATED
    (tmp_course / "course.yaml").write_text("changed", encoding="utf-8")
    assert registry.status("demo/admin", course_digest(tmp_course)) is CourseMaturity.DRAFT
```

- [ ] **Step 2: Verify RED and implement strict non-secret records**

Run: `.venv/bin/python -m pytest tests/test_course_certification.py tests/test_curriculum.py -q`

Certification entries contain only path, SHA-256 digest, status, ISO date,
LearnLab revision, guest capabilities, and note. Reject unknown keys and strings
matching URL, IP-address, VMID-label, or token-secret patterns.

- [ ] **Step 3: Verify and commit**

```bash
git add src/learnlab/curriculum.py src/learnlab/course_certification.py src/learnlab/collections/certifications.yaml tests/test_curriculum.py tests/test_course_certification.py
git commit -m "feat: track curriculum certification maturity"
```

---

### Task 2: Correct Debian and NixOS nftables Courses

**Files:**
- Modify: `src/learnlab/collections/nftables-debian13/**`
- Modify: `src/learnlab/collections/nftables-nixos/**`
- Create: `tests/test_shipped_nftables_courses.py`

- [ ] **Step 1: Write regression tests for the known false exercises**

```python
def test_nftables_courses_do_not_test_prerouting_through_loopback(courses):
    for course in courses:
        assert not any("prerouting" in step.instructions and "127.0.0.1:8081" in step.instructions for lesson in course.lessons for step in lesson.steps)

def test_drop_log_probe_is_not_loopback(courses):
    for course in courses:
        assert not any("nft-drop" in step.instructions and "127.0.0.1:9999" in step.instructions for lesson in course.lessons for step in lesson.steps)
```

- [ ] **Step 2: Verify RED and correct packet-flow teaching**

Run: `.venv/bin/python -m pytest tests/test_shipped_nftables_courses.py -q`

If no honest single-VM remote probe exists, remove the NAT lesson from ready
ordering, keep its files draft with a multi-machine blocker, and do not replace
objective checks with attestation. Use a non-loopback source for drop logging and
tighten regexes so negated or unrelated answers do not pass.

- [ ] **Step 3: Validate and commit the family**

Run: `.venv/bin/learnlab validate nftables-debian13/nftables-basics`

Run: `.venv/bin/learnlab validate nftables-nixos/nftables-basics`

```bash
git add src/learnlab/collections/nftables-debian13 src/learnlab/collections/nftables-nixos tests/test_shipped_nftables_courses.py
git commit -m "fix: correct nftables course packet-flow exercises"
```

---

### Task 3: Correct Debian and NixOS nginx Courses

**Files:**
- Modify: `src/learnlab/collections/nginx/**`
- Modify: `src/learnlab/collections/nginx-nixos/**`
- Create: `tests/test_shipped_nginx_courses.py`

- [ ] **Step 1: Write the NixOS option-path regression test**

```python
def test_nixos_nginx_response_is_nested_under_virtual_host(nixos_nginx_course):
    text = all_instructions(nixos_nginx_course)
    assert 'services.nginx.virtualHosts."learnlab.local"' in text
    assert "services.nginx = {\n  enable = true;\n  locations" not in text
```

- [ ] **Step 2: Verify RED and fix the NixOS snippet**

Run: `.venv/bin/python -m pytest tests/test_shipped_nginx_courses.py -q`

Use a named virtual host and `locations."/"` beneath it. Add `os.debian.13` or
`os.nixos` plus `tool.curl` capabilities, clarify Debian naming, and replace
brittle source greps with runtime/evaluated checks where available.

- [ ] **Step 3: Validate and commit the family**

Run both nginx course paths through `learnlab validate`, then:

```bash
git add src/learnlab/collections/nginx src/learnlab/collections/nginx-nixos tests/test_shipped_nginx_courses.py
git commit -m "fix: validate nginx course configurations"
```

---

### Task 4: Review Debian and NixOS systemd Courses

**Files:**
- Modify: `src/learnlab/collections/systemd-debian/**`
- Modify: `src/learnlab/collections/systemd-nixos/**`
- Create: `tests/test_shipped_systemd_courses.py`

- [ ] **Step 1: Add invariants for target OS, readiness, and safe commands**

```python
@pytest.mark.parametrize("path, os_cap", [
    ("systemd-debian/service-authoring", "os.debian.13"),
    ("systemd-nixos/service-authoring", "os.nixos"),
])
def test_systemd_course_declares_target_os(catalog, path, os_cap):
    assert os_cap in catalog.load_course(path).environment.guest_capabilities
```

- [ ] **Step 2: Review every instruction and verification**

Check generated-unit assumptions, `nixos-rebuild test` wording, oneshot state,
restart counting, dependency semantics, file ownership, sandboxing, timers, and
capstone recovery. Tighten text regexes and ensure commands remain valid after a
save/resume retry.

- [ ] **Step 3: Validate and commit the family**

Run the focused test plus offline validation for both paths, then:

```bash
git add src/learnlab/collections/systemd-debian src/learnlab/collections/systemd-nixos tests/test_shipped_systemd_courses.py
git commit -m "fix: harden systemd course verification"
```

---

### Task 5: Revise the Course Authoring Guide

**Files:**
- Modify: `docs/LearnLab-Course-Authoring-Guide.md`
- Create: `tests/test_course_authoring_docs.py`

- [ ] **Step 1: Add documentation contract tests**

```python
def test_guide_uses_canonical_tree_and_validation_command(guide_text):
    assert "src/learnlab/collections/" in guide_text
    assert "keep the two in sync" not in guide_text.lower()
    assert "learnlab validate" in guide_text
```

- [ ] **Step 2: Rewrite affected sections**

Document maturity, digest certification, guest capabilities, three validation
levels, versioning consequences, and the live checklist. Label the nested-
virtualization walkthrough illustrative until it has its own certification.

- [ ] **Step 3: Verify and commit**

```bash
git add docs/LearnLab-Course-Authoring-Guide.md tests/test_course_authoring_docs.py
git commit -m "docs: align course authoring with certification"
```

---

### Task 6: Live Acceptance and Certification

**Files:**
- Modify after each successful run: `src/learnlab/collections/certifications.yaml`
- Create: `docs/course-validation/2026-09-08-pending-courses.md`

- [ ] **Step 1: Stop for explicit destructive-test authorization**

Present the exact course path, scratch profile, expected template capabilities,
and cleanup behavior. Do not continue until the operator explicitly approves.

- [ ] **Step 2: Execute each approved course protocol**

For each course, run provider-aware validation, start fresh, deliberately fail a
check, resume mid-lesson, complete all lessons, destroy, and verify absence. Do
not run courses in parallel against shared infrastructure.

- [ ] **Step 3: Record only successful digest certifications**

Calculate the canonical digest after content stops changing. Record failures and
blockers in the report, but leave their maturity `draft`.

- [ ] **Step 4: Run the full offline gate and commit**

Run pytest excluding live tests, Ruff, mypy, wheel packaging, and diff check.

```bash
git add src/learnlab/collections/certifications.yaml docs/course-validation/2026-09-08-pending-courses.md
git commit -m "docs: certify reviewed course curricula"
```
