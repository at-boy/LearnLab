# Course Discovery and Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let learners browse courses, inspect lessons and progress, and continue recent work from plain `learnlab`.

**Architecture:** Add read-only catalog/state query services, keep rendering in focused CLI presentation helpers, and route every selected action through existing command/session services. Offline navigation never constructs provider dependencies.

**Tech Stack:** Python 3.13, Typer, SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-course-discovery-continuation-design.md`

## Global Constraints

- Complete catalog discovery from `2026-09-08-course-authoring-validation.md` first.
- Plain `learnlab` prompts only when stdin and stdout are TTYs.
- Listing, progress, and selection never resolve provider secrets.
- Preserve existing explicit commands and course-owned lesson ordering.
- Removed curriculum is displayed as historical unavailable state.
- Use an isolated worktree and TDD; do not push or merge implicitly.

---

### Task 1: Read-Only Course Progress Projection

**Files:**
- Modify: `src/learnlab/state.py`
- Create: `src/learnlab/navigation.py`
- Modify: `tests/test_state.py`
- Create: `tests/test_navigation.py`

**Interfaces:**
- Produces: `StoredCourseActivity`, `CourseNavigationItem`, `CourseProgressSummary`.
- Produces: `StateStore.course_activities() -> tuple[StoredCourseActivity, ...]`.
- Produces: `build_course_navigation(catalog, activities) -> tuple[CourseNavigationItem, ...]`.

- [ ] **Step 1: Write activity ordering and orphan tests**

```python
def test_started_courses_sort_by_latest_activity(store):
    seed_activity(store, "demo/old", "2026-09-01T00:00:00Z")
    seed_activity(store, "demo/new", "2026-09-02T00:00:00Z")
    assert [x.course_path for x in store.course_activities()] == ["demo/new", "demo/old"]

def test_navigation_retains_removed_course_as_unavailable(catalog, activities):
    [item] = build_course_navigation(catalog, activities)
    assert item.available is False
```

- [ ] **Step 2: Verify RED and implement one read-only query**

Run: `.venv/bin/python -m pytest tests/test_state.py tests/test_navigation.py -k course -q`

Aggregate existing progress, cursors, verification timestamps, and environments
without changing schema unless query performance requires a tested index.

- [ ] **Step 3: Verify and commit**

```bash
git add src/learnlab/state.py src/learnlab/navigation.py tests/test_state.py tests/test_navigation.py
git commit -m "feat: project course navigation state"
```

---

### Task 2: Courses and Lessons Commands

**Files:**
- Modify: `src/learnlab/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Produces: `learnlab courses [--include-drafts] [--format human|json]`.
- Produces: `learnlab lessons COLLECTION/COURSE [--format human|json]`.

- [ ] **Step 1: Write offline command tests**

```python
def test_courses_lists_status_without_provider(runner, monkeypatch):
    monkeypatch.setattr(cli, "load_settings", forbidden)
    result = runner.invoke(app, ["courses"])
    assert result.exit_code == 0
    assert "in progress" in result.stdout
```

- [ ] **Step 2: Verify RED and implement deterministic renderers**

Run: `.venv/bin/python -m pytest tests/test_cli.py -k 'courses or lessons' -q`

Human output includes path, title, maturity, and progress. Lesson output uses
course order and marks completed, in-progress, and first incomplete. JSON uses
`schema_version: 1` and stable ordering.

- [ ] **Step 3: Verify and commit**

```bash
git add src/learnlab/cli.py tests/test_cli.py
git commit -m "feat: list courses and lessons"
```

---

### Task 3: Real Progress Command

**Files:**
- Modify: `src/learnlab/cli.py`
- Modify: `tests/test_cli_progress.py`
- Modify: `README.md`

- [ ] **Step 1: Write the missing bare-command test**

```python
def test_progress_without_subcommand_lists_all_course_progress(runner):
    result = runner.invoke(app, ["progress"])
    assert result.exit_code == 0
    assert "Completed lessons" in result.stdout
```

- [ ] **Step 2: Verify RED and add a progress callback**

Run: `.venv/bin/python -m pytest tests/test_cli_progress.py -q`

Configure the Typer group with `invoke_without_command=True`; render only when no
subcommand was selected so `progress complete` remains unchanged.

- [ ] **Step 3: Verify and commit**

```bash
git add src/learnlab/cli.py tests/test_cli_progress.py README.md
git commit -m "fix: make progress command show saved state"
```

---

### Task 4: Continue Most Recent Course

**Files:**
- Modify: `src/learnlab/navigation.py`
- Modify: `src/learnlab/cli.py`
- Modify: `tests/test_navigation.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Produces: `select_continuation(items) -> CourseNavigationItem | None`.
- Produces: `learnlab continue [--provider PROFILE]`.

- [ ] **Step 1: Write selection tests**

```python
def test_continue_selects_latest_incomplete_started_course(items):
    assert select_continuation(items).course_path == "nixos/foundations"

def test_continue_ignores_completed_and_unavailable_courses(items):
    assert select_continuation(items) is None
```

- [ ] **Step 2: Verify RED and delegate to the session entry point**

Run: `.venv/bin/python -m pytest tests/test_navigation.py tests/test_cli.py -k continue -q`

Do not reimplement session behavior. Pass the selected path to
`_run_course_session(..., require_existing=True)` and preserve provider ownership
checks. Emit a clear offline error when no candidate exists.

- [ ] **Step 3: Verify and commit**

```bash
git add src/learnlab/navigation.py src/learnlab/cli.py tests/test_navigation.py tests/test_cli.py
git commit -m "feat: continue recent course progress"
```

---

### Task 5: No-Argument Interactive Home

**Files:**
- Create: `src/learnlab/home.py`
- Modify: `src/learnlab/cli.py`
- Create: `tests/test_home.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Produces: `HomeAction`, `HomePrompt`, `run_home(items, prompt) -> HomeAction`.
- Extends root Typer callback with `invoke_without_command=True`.

- [ ] **Step 1: Write TTY, non-TTY, and cancellation tests**

```python
def test_plain_learnlab_opens_home_only_on_tty(runner, tty_streams):
    result = runner.invoke(app, [], input="1\n")
    assert "Continue" in result.stdout

def test_home_eof_exits_without_state_change(home, store):
    assert home.run(prompt=EofPrompt()) is HomeAction.EXIT
    assert store.course_activities() == ()
```

- [ ] **Step 2: Verify RED and implement presentation-only home logic**

Run: `.venv/bin/python -m pytest tests/test_home.py tests/test_cli.py -k home -q`

The home module returns an action; CLI dispatch invokes existing functions.
Non-TTY plain invocation prints concise help and exits zero.

- [ ] **Step 3: Verify and commit**

```bash
git add src/learnlab/home.py src/learnlab/cli.py tests/test_home.py tests/test_cli.py
git commit -m "feat: add interactive LearnLab home"
```

---

### Task 6: Full Regression and Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/LearnLab-Course-Authoring-Guide.md`

- [ ] **Step 1: Document interactive and scriptable workflows**

Show `learnlab`, `courses`, `lessons`, `continue`, and `progress`; state clearly
which commands are offline and how removed/draft courses appear.

- [ ] **Step 2: Run the full gate**

Run offline pytest, Ruff, `mypy src`, wheel tests, and `git diff --check`.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/LearnLab-Course-Authoring-Guide.md
git commit -m "docs: explain course discovery and continuation"
```
