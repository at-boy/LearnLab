# Course Authoring and Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one canonical curriculum tree and add offline plus read-only provider-aware validation.

**Architecture:** Extend `CurriculumCatalog` with deterministic discovery, model provider-neutral guest capabilities, and place validation findings behind a side-effect-free service. The CLI renders that service in human or versioned JSON form; provider-aware validation reuses only the existing read-only health contract.

**Tech Stack:** Python 3.13, Typer, PyYAML, importlib.resources, pytest, Ruff, mypy, Hatchling.

**Spec:** `docs/superpowers/specs/2026-09-08-course-authoring-validation-design.md`

## Global Constraints

- `src/learnlab/collections/` is the only maintained curriculum tree.
- Offline validation must not load settings, state, secrets, SSH, or providers.
- Online validation is read-only and requires an explicit named profile.
- Curriculum contains no profile, VMID, node, storage, network, URL, or secret.
- Preserve Python 3.13 and current dependency version bounds.
- Use an isolated worktree and TDD; do not push or merge implicitly.

---

### Task 1: Canonical Curriculum Tree and Discovery

**Files:**
- Modify: `src/learnlab/curriculum.py`
- Modify: `tests/test_curriculum.py`
- Modify: `tests/test_packaging.py`
- Delete after migration: `collections/**`

**Interfaces:**
- Produces: `CourseSummary(collection_id: str, course_id: str, title: str)`.
- Produces: `CurriculumCatalog.list_courses() -> tuple[CourseSummary, ...]`.

- [x] **Step 1: Write failing discovery tests**

```python
def test_list_courses_is_complete_and_stably_sorted(catalog):
    assert [item.path for item in catalog.list_courses()] == [
        "alpha/one", "alpha/two", "zeta/last"
    ]

def test_list_courses_reports_malformed_collection(catalog_with_bad_entry):
    with pytest.raises(CurriculumError, match="bad/collection.yaml"):
        catalog_with_bad_entry.list_courses()
```

- [x] **Step 2: Run the focused tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_curriculum.py -k list_courses -q`

Expected: failures because `CourseSummary` and `list_courses` do not exist.

- [x] **Step 3: Implement discovery and migrate the tree**

Implement `CourseSummary.path` as `f"{collection_id}/{course_id}"`. Enumerate
only directories, validate every `collection.yaml` and `course.yaml` through the
existing strict loader, and sort by IDs. Move all curriculum into
`src/learnlab/collections/`; remove the duplicate-tree equality test and retain
wheel-content/install tests against the canonical tree.

- [x] **Step 4: Verify GREEN and commit**

Run: `.venv/bin/python -m pytest tests/test_curriculum.py tests/test_packaging.py -q`

```bash
git add src/learnlab/curriculum.py src/learnlab/collections tests/test_curriculum.py tests/test_packaging.py
git add -u collections
git commit -m "refactor: make packaged curriculum canonical"
```

---

### Task 2: Guest Capability Contract and Requirements Migration

**Files:**
- Modify: `src/learnlab/curriculum.py`
- Modify: `src/learnlab/config.py`
- Modify: `tests/test_curriculum.py`
- Modify: `tests/test_config.py`

**Interfaces:**
- Produces: `EnvironmentPolicy.guest_capabilities: tuple[str, ...]`.
- Produces: `ProxmoxProfile.template_capabilities: tuple[str, ...]`.
- Produces: `Course.curriculum_warnings: tuple[str, ...]` during the legacy migration.

- [x] **Step 1: Write strict schema and compatibility tests**

```python
def test_vm_environment_loads_guest_capabilities(course):
    assert course.environment.guest_capabilities == ("os.nixos", "tool.curl")

def test_none_environment_rejects_guest_capabilities(curriculum_builder):
    curriculum_builder.scope("none", guest_capabilities=["os.nixos"])
    with pytest.raises(CurriculumError, match="forbidden"):
        curriculum_builder.load()

def test_profile_loads_template_capabilities(settings_file):
    assert load_settings(settings_file).provider("lab").template_capabilities == (
        "os.nixos", "tool.curl"
    )
```

- [x] **Step 2: Verify RED**

Run: `.venv/bin/python -m pytest tests/test_curriculum.py tests/test_config.py -k capabilities -q`

- [x] **Step 3: Implement immutable capability parsing**

Use the existing capability-ID grammar, reject duplicates and unknown keys, and
require at least one `os.*` capability for VM scopes. Accept legacy
`requirements` only when `guest_capabilities` is absent, normalize it, and attach
the warning `requirements is deprecated; use environment.guest_capabilities`.

- [x] **Step 4: Verify and commit**

Run: `.venv/bin/python -m pytest tests/test_curriculum.py tests/test_config.py -q`

```bash
git add src/learnlab/curriculum.py src/learnlab/config.py tests/test_curriculum.py tests/test_config.py
git commit -m "feat: declare guest template capabilities"
```

---

### Task 3: Side-Effect-Free Validation Service

**Files:**
- Create: `src/learnlab/course_validation.py`
- Create: `tests/test_course_validation.py`
- Modify: `src/learnlab/providers/proxmox.py`

**Interfaces:**
- Produces: `FindingSeverity`, `CurriculumFinding`, `ValidationReport`.
- Produces: `validate_catalog(catalog, course_path=None) -> ValidationReport`.
- Produces: `known_provider_checks() -> frozenset[str]` without constructing a provider.

- [x] **Step 1: Write aggregation and lint tests**

```python
def test_validation_aggregates_independent_findings(broken_catalog):
    report = validate_catalog(broken_catalog)
    assert {(f.course_path, f.severity.value) for f in report.findings} == {
        ("demo/regex", "warning"), ("demo/check", "error")
    }

def test_offline_validation_flags_unanchored_yes_no_regex(catalog):
    [finding] = validate_catalog(catalog).warnings
    assert finding.code == "broad-yes-no-regex"
```

- [x] **Step 2: Verify RED and implement findings**

Run: `.venv/bin/python -m pytest tests/test_course_validation.py -q`

Findings are frozen dataclasses sorted by course path, source path, code, and
message. Catch errors per discoverable course so one malformed course does not
hide findings from another. Implement only the lint checks listed in the spec.

- [x] **Step 3: Verify and commit**

Run: `.venv/bin/python -m pytest tests/test_course_validation.py tests/providers/test_proxmox.py -q`

```bash
git add src/learnlab/course_validation.py src/learnlab/providers/proxmox.py tests/test_course_validation.py tests/providers/test_proxmox.py
git commit -m "feat: validate complete curriculum catalogs"
```

---

### Task 4: Offline Validate CLI and JSON Contract

**Files:**
- Modify: `src/learnlab/cli.py`
- Modify: `tests/test_cli.py`
- Create: `tests/snapshots/validate-report-v1.json`

**Interfaces:**
- Produces: `learnlab validate [COURSE] [--format human|json]`.
- JSON root: `{"schema_version": 1, "ok": bool, "findings": [...]}`.

- [x] **Step 1: Write CLI isolation and output tests**

```python
def test_validate_all_is_offline(runner, monkeypatch):
    monkeypatch.setattr(cli, "load_settings", forbidden)
    monkeypatch.setattr(cli, "state_store_factory", forbidden)
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0

def test_validate_json_is_versioned_and_deterministic(runner):
    first = runner.invoke(app, ["validate", "--format", "json"])
    second = runner.invoke(app, ["validate", "--format", "json"])
    assert first.stdout == second.stdout
```

- [x] **Step 2: Verify RED and implement the command**

Run: `.venv/bin/python -m pytest tests/test_cli.py -k validate -q`

Render source-relative paths, course path, severity, code, message, and remedy.
Map errors to exit 1 and Typer usage errors to exit 2.

- [x] **Step 3: Verify and commit**

Run: `.venv/bin/python -m pytest tests/test_cli.py tests/test_course_validation.py -q`

```bash
git add src/learnlab/cli.py tests/test_cli.py tests/snapshots/validate-report-v1.json
git commit -m "feat: add offline curriculum validation command"
```

---

### Task 5: Read-Only Provider-Aware Validation

**Files:**
- Modify: `src/learnlab/course_validation.py`
- Modify: `src/learnlab/cli.py`
- Modify: `tests/test_course_validation.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Produces: `validate_profile_compatibility(report, profile, health) -> ValidationReport`.
- Extends: `learnlab validate [COURSE] --provider PROFILE`.

- [x] **Step 1: Write capability and read-only tests**

```python
def test_profile_validation_reports_missing_capability(report, profile, health):
    profile = replace(profile, template_capabilities=("os.debian.13",))
    checked = validate_profile_compatibility(report, profile, health)
    assert checked.errors[0].code == "missing-guest-capability"

def test_provider_mode_performs_no_mutation(provider_spy, runner):
    result = runner.invoke(app, ["validate", "demo/admin", "--provider", "lab"])
    assert result.exit_code == 0
    assert provider_spy.mutations == []
```

- [x] **Step 2: Verify RED and implement online validation**

Run: `.venv/bin/python -m pytest tests/test_course_validation.py tests/test_cli.py -k provider -q`

Run offline validation first. Resolve the explicit profile and secret only if it
passes sufficiently to identify capabilities, call `health_check()`, redact all
errors, and map operational failure to exit 3.

- [x] **Step 3: Verify and commit**

Run: `.venv/bin/python -m pytest tests/test_course_validation.py tests/test_cli.py tests/providers/test_proxmox.py -q`

```bash
git add src/learnlab/course_validation.py src/learnlab/cli.py tests/test_course_validation.py tests/test_cli.py
git commit -m "feat: validate configured course templates"
```

---

### Task 6: Documentation and Full Gate

**Files:**
- Modify: `README.md`
- Modify: `docs/LearnLab-Course-Authoring-Guide.md`
- Modify: `tests/test_packaging.py`

- [x] **Step 1: Update documentation with exact commands and migration**

Document the canonical path, offline/online validation, exit codes, JSON mode,
guest capabilities, legacy `requirements` warning, and the read-only boundary.

- [x] **Step 2: Run the full verification gate**

Run: `.venv/bin/python -m pytest -m 'not live' -q`

Run: `.venv/bin/ruff check .`

Run: `.venv/bin/mypy src`

Run: `git diff --check`

Expected: every command succeeds; no live Proxmox test runs.

- [x] **Step 3: Commit documentation**

```bash
git add README.md docs/LearnLab-Course-Authoring-Guide.md tests/test_packaging.py
git commit -m "docs: document course validation workflow"
```
