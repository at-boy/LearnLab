# NixOS Administration Curriculum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the original hands-on NixOS administration path as three progressively advanced, validated courses.

**Architecture:** Extend curriculum metadata and hints only where earlier workstreams have not already done so, then author each course as an independent reviewed unit. Data-driven tests enforce learning order and safety; digest-matched live certification is required before ready status.

**Tech Stack:** LearnLab YAML curriculum, Python 3.13/pytest content tests, NixOS 26.05-compatible configuration, disposable Proxmox VM.

**Spec:** `docs/superpowers/specs/2026-09-08-nixos-administration-curriculum-design.md`

## Global Constraints

- Complete course validation and certification workstreams first.
- Keep concrete template and Proxmox values out of curriculum.
- Target experienced Linux administrators with zero NixOS experience.
- Teach classic NixOS before Nix language internals, then flakes and fleet.
- Early lessons include precise commands, expected outcomes, and progressive hints.
- Live testing is destructive and requires explicit authorization and cleanup.
- Use an isolated worktree; do not push or merge implicitly.

---

### Task 1: Curriculum Metadata, Prerequisites, Revision, and Hints

**Files:**
- Modify: `src/learnlab/curriculum.py`
- Modify: `src/learnlab/session.py`
- Modify: `src/learnlab/cli.py`
- Modify: `tests/test_curriculum.py`
- Modify: `tests/test_session.py`

**Interfaces:**
- Adds course fields: `summary`, `audience`, `objectives`, `estimated_minutes`, `prerequisites`, `revision`, `maturity`.
- Adds verification fields: `expected`, `hints: tuple[str, ...]`.
- Adds session action `SHOW_HINT` and persisted hint index keyed by full verification path and curriculum revision.

- [ ] **Step 1: Write strict metadata and hint tests**

```python
def test_course_loads_authoring_metadata(course):
    assert course.revision == 1
    assert course.estimated_minutes == 180
    assert course.prerequisites == ()

def test_failed_check_reveals_hints_in_order(session):
    assert session.next_hint(CHECK_PATH) == "Inspect the option name."
    assert session.next_hint(CHECK_PATH) == "Run nixos-option services.openssh.enable."
```

- [ ] **Step 2: Verify RED and implement exact-key parsing**

Run: `.venv/bin/python -m pytest tests/test_curriculum.py tests/test_session.py -k 'metadata or hint' -q`

Require positive revision/minutes, stable prerequisite course paths, non-empty
unique objectives/hints, and no hints containing provider deployment values.
Persist hint position additively; revision changes reset only hint/check
interpretation explicitly covered by migration tests.

- [ ] **Step 3: Verify and commit**

```bash
git add src/learnlab/curriculum.py src/learnlab/session.py src/learnlab/cli.py tests/test_curriculum.py tests/test_session.py
git commit -m "feat: support guided curriculum metadata and hints"
```

---

### Task 2: Author Administration Foundations

**Files:**
- Create: `src/learnlab/collections/nixos/collection.yaml`
- Create: `src/learnlab/collections/nixos/courses/administration-foundations/course.yaml`
- Create: `src/learnlab/collections/nixos/courses/administration-foundations/lessons/*/lesson.yaml`
- Create: `tests/test_nixos_curriculum.py`

- [ ] **Step 1: Write course-order and safety tests**

```python
def test_foundations_has_deliberate_learning_order(catalog):
    course = catalog.load_course("nixos/administration-foundations")
    assert [lesson.id for lesson in course.lessons] == [
        "first-contact", "configuration-and-options", "packages",
        "rebuild-modes", "generations-and-rollback", "users-and-ssh",
        "services-and-logs", "networking-and-firewall", "maintenance-and-recovery",
    ]

def test_early_foundation_checks_have_progressive_hints(catalog):
    course = catalog.load_course("nixos/administration-foundations")
    assert all(v.hints for l in course.lessons[:4] for s in l.steps for v in s.verifications)
```

- [ ] **Step 2: Verify RED and author lessons 1-4**

Run: `.venv/bin/python -m pytest tests/test_nixos_curriculum.py -q`

Teach first contact, configuration/options, packages, and all four rebuild modes.
Prefer `nixos-option`, evaluated state, `readlink`, `systemctl`, and command
presence over formatting-sensitive greps.

- [ ] **Step 3: Author lessons 5-9 and recovery paths**

Add generations/rollback, users/SSH, services/journal, network/firewall, and
maintenance/recovery. Arm and explain recovery before connectivity-sensitive
changes; never make intentional remote lockout a required automated step.

- [ ] **Step 4: Validate and commit as draft**

Run: `.venv/bin/learnlab validate nixos/administration-foundations`

```bash
git add src/learnlab/collections/nixos tests/test_nixos_curriculum.py
git commit -m "feat: add NixOS administration foundations course"
```

---

### Task 3: Author Nix Language and Store

**Files:**
- Create: `src/learnlab/collections/nixos/courses/nix-language-and-store/course.yaml`
- Create: `src/learnlab/collections/nixos/courses/nix-language-and-store/lessons/*/lesson.yaml`
- Modify: `tests/test_nixos_curriculum.py`

- [ ] **Step 1: Add prerequisite and topic-order tests**

```python
def test_language_course_follows_foundations(catalog):
    course = catalog.load_course("nixos/nix-language-and-store")
    assert course.prerequisites == ("nixos/administration-foundations",)
    assert course.lessons[-2].id == "evaluation-and-realization"
    assert course.lessons[-1].id == "profiles-and-caches"
```

- [ ] **Step 2: Author administration-focused exercises**

Cover types, lists/sets, functions, bindings, imports, module merging, store
paths/derivations, evaluation/realization, profiles, shells, builds, and caches.
Use `nix eval`, `nix repl`, `nix build`, and filesystem inspections with bounded
expressions and no uncontrolled network fetches.

- [ ] **Step 3: Validate and commit as draft**

```bash
git add src/learnlab/collections/nixos/courses/nix-language-and-store tests/test_nixos_curriculum.py
git commit -m "feat: add Nix language and store course"
```

---

### Task 4: Author Flakes and Fleet

**Files:**
- Create: `src/learnlab/collections/nixos/courses/flakes-and-fleet/course.yaml`
- Create: `src/learnlab/collections/nixos/courses/flakes-and-fleet/lessons/*/lesson.yaml`
- Modify: `tests/test_nixos_curriculum.py`

- [ ] **Step 1: Add flake sequencing and locked-input tests**

```python
def test_flakes_course_requires_language_course(catalog):
    course = catalog.load_course("nixos/flakes-and-fleet")
    assert course.prerequisites == ("nixos/nix-language-and-store",)
    assert "flake-lock" in [lesson.id for lesson in course.lessons]
```

- [ ] **Step 2: Author deterministic flake exercises**

Cover flake structure, inputs/outputs, lock behavior, updates/rollback, multiple
`nixosConfigurations`, shared modules, roles, checks, and Git. Pin initial input
state in the template or course-owned local fixture so ordinary validation does
not depend on a changing network source.

- [ ] **Step 3: Validate and commit as draft**

```bash
git add src/learnlab/collections/nixos/courses/flakes-and-fleet tests/test_nixos_curriculum.py
git commit -m "feat: add flakes and fleet course"
```

---

### Task 5: Nix Evaluation Smoke Harness

**Files:**
- Create: `tests/nixos/test_curriculum_snippets.py`
- Create: `tests/nixos/README.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Adds pytest marker `nixos`: requires a disposable NixOS execution environment but not Proxmox mutation itself.

- [ ] **Step 1: Extract fenced Nix examples and write smoke tests**

```python
@pytest.mark.nixos
def test_foundation_nix_snippets_evaluate(nixos_runner, catalog):
    for snippet in nix_snippets(catalog.load_course("nixos/administration-foundations")):
        assert nixos_runner.evaluate_module(snippet).returncode == 0
```

- [ ] **Step 2: Implement a bounded runner contract**

The harness executes only reviewed extracted snippets, uses fixed timeouts,
captures bounded output, and is skipped with a clear reason when no NixOS runner
is configured. It never runs in the ordinary offline suite.

- [ ] **Step 3: Verify and commit**

```bash
git add tests/nixos pyproject.toml
git commit -m "test: evaluate NixOS curriculum snippets"
```

---

### Task 6: Live Course Acceptance and Publication Readiness

**Files:**
- Modify after success: `src/learnlab/collections/certifications.yaml`
- Create: `docs/course-validation/nixos-administration.md`
- Modify: `README.md`

- [ ] **Step 1: Request explicit authorization for each course run**

State the scratch profile, course digest, destructive lifecycle, and cleanup
plan. Run courses sequentially only after approval.

- [ ] **Step 2: Execute the full acceptance protocol**

For each course: provider-aware validate, fresh start, deliberate failed check,
progressive hints, mid-lesson resume, all checks, destroy, and absence check.

- [ ] **Step 3: Record digest-matched successes and blockers**

Keep failures draft. Certification notes contain no environment identity.

- [ ] **Step 4: Run full offline gate and commit**

```bash
git add src/learnlab/collections/certifications.yaml docs/course-validation/nixos-administration.md README.md
git commit -m "docs: certify NixOS administration curriculum"
```
