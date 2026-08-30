# Interactive Course Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LearnLab provisioning visibly active and turn `start`/`resume` into persisted interactive sessions that validate ordered lesson work and reuse or replace environments according to curriculum policy.

**Architecture:** Extend immutable curriculum models with explicit environment policy and typed verification definitions; extend SQLite with additive session, step, and verification state; add structured lifecycle progress events; implement focused SSH and validator adapters; coordinate them in a provider-neutral session service; keep Typer responsible only for prompts and rendering.

**Tech Stack:** Python 3.13, Typer, HTTPX, PyYAML, platformdirs, SQLite, stdlib subprocess/regex/importlib.resources, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-30-interactive-course-sessions-design.md`

## Global Constraints

- Preserve `Platform > Collection > Course > Lesson > Steps > Verifications` with explicit YAML ordering and stable identifiers.
- Curriculum owns environment lifetime through `course`, `lesson`, or `none`; provider deployment values never enter curriculum.
- A step may contain multiple ordered verifications of any supported type; all must pass.
- Never execute learner-provided text as a command.
- Remote commands use isolated `known_hosts`, strict host-key checking, batch mode, bounded output, and timeouts.
- Provider checks are read-only.
- Secrets, private keys, authorization headers, and unbounded provider/SSH output are never persisted or emitted.
- Existing provider fingerprint/name ownership, clone uncertainty, destroy/reset safety, and legacy database migration guarantees must remain intact.
- Semantic production changes follow observed RED/GREEN TDD; normal tests are offline and the live test remains explicitly opted in.

## File Map

```text
src/learnlab/curriculum.py            environment and verification schema/models
src/learnlab/state.py                 additive session/step/verification migration and repository
src/learnlab/progress.py              structured lifecycle progress events and observer protocol
src/learnlab/lifecycle.py             progress emission and scoped environment operations
src/learnlab/ssh.py                   non-interactive remote-command executor
src/learnlab/validation.py            validator protocol, registry, four validators
src/learnlab/session.py               interactive-neutral session state machine
src/learnlab/cli.py                   start/resume prompts, progress renderer, manual override
src/learnlab/providers/base.py        read-only named provider-check protocol
src/learnlab/providers/proxmox.py     Proxmox provider-check implementations and heartbeat events
collections/proxmox/...               updated authoring curriculum
src/learnlab/collections/proxmox/...  packaged curriculum mirror
README.md                              interactive workflow and schema documentation
tests/test_curriculum.py               scope and verification schema coverage
tests/test_state.py                    migration and persisted verification coverage
tests/test_progress.py                 progress event safety/order
tests/test_ssh.py                      SSH execution contract
tests/test_validation.py               four validator types and repeated/all-required behavior
tests/test_session.py                  resume and environment-scope state machine
tests/test_lifecycle.py                event emission and safe scope transitions
tests/test_cli.py                      spinner/start/resume/manual completion UX
tests/test_packaging.py                packaged curriculum synchronization and install behavior
```

---

### Task 1: Curriculum Environment and Verification Schema

**Files:**
- Modify: `src/learnlab/curriculum.py`
- Modify: `tests/test_curriculum.py`

**Interfaces:**
- Produces: `EnvironmentScope`, `EnvironmentPolicy`, `VerificationType`, `Verification`, enriched `Step`, and `Lesson.environment`/`Course.environment`.
- `Course.effective_environment(lesson) -> EnvironmentPolicy`.
- Verification stores normalized type-specific fields without deployment data.

- [ ] **Step 1: Write failing environment-scope tests**

```python
def test_lesson_environment_override_wins_over_course(tmp_curriculum):
    course = tmp_curriculum.load_course("demo/admin")
    assert course.environment.scope is EnvironmentScope.COURSE
    assert course.effective_environment(course.lessons[0]).scope is EnvironmentScope.NONE


@pytest.mark.parametrize("scope", ["course", "lesson"])
def test_vm_scope_requires_provider_capability(scope, curriculum_builder):
    curriculum_builder.course_environment({"scope": scope})
    with pytest.raises(CurriculumError, match="provider_capability"):
        curriculum_builder.load()


def test_none_scope_forbids_provider_capability(curriculum_builder):
    curriculum_builder.course_environment(
        {"scope": "none", "provider_capability": "proxmox.vm"}
    )
    with pytest.raises(CurriculumError, match="forbidden"):
        curriculum_builder.load()
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python3.13 -m pytest tests/test_curriculum.py -k environment -q`

Expected: import/attribute failures because environment models do not exist.

- [ ] **Step 3: Implement strict environment models and parsing**

Use string enums. `provider_capability` follows the existing capability grammar. Course requires `environment`; lesson environment is optional. Reject unknown keys and invalid cross-field combinations with source-path context.

- [ ] **Step 4: Write failing repeated-verification and type-schema tests**

```python
def test_step_accepts_repeated_validator_types_in_order(course):
    checks = course.lessons[0].steps[0].verifications
    assert [item.type for item in checks] == [
        VerificationType.REMOTE_COMMAND,
        VerificationType.REMOTE_COMMAND,
        VerificationType.TEXT_EVIDENCE,
    ]


def test_duplicate_verification_ids_are_rejected(curriculum_builder):
    curriculum_builder.verifications([REMOTE_A, REMOTE_A])
    with pytest.raises(CurriculumError, match="duplicate verification id"):
        curriculum_builder.load()


def test_remote_command_is_rejected_for_effective_none_scope(curriculum_builder):
    curriculum_builder.scope("none").verifications([REMOTE_A])
    with pytest.raises(CurriculumError, match="requires an environment"):
        curriculum_builder.load()
```

Add parametrized tests for required/forbidden fields of all four types, exactly-one-of `equals`/`matches`, regex compile failure, 1–300 timeout range, 8 KiB evidence rule constant, empty verification list, unknown type, and unknown keys.

- [ ] **Step 5: Implement normalized verification parsing**

`Verification` has common fields plus optional typed fields: `command`, `timeout_seconds`, `prompt`, `equals`, `matches`, and `check`. The parser validates combinations and preserves declared order. `Step.content` is renamed to `instructions` in models while the loader temporarily accepts the old `content` key as a migration alias only when `instructions` is absent; reject both together.

- [ ] **Step 6: Verify GREEN and commit**

Run: `python3.13 -m pytest tests/test_curriculum.py -q && python3.13 -m pytest -m 'not live' -q`

```bash
git add src/learnlab/curriculum.py tests/test_curriculum.py
git commit -m "feat: model environment and verification curriculum"
```

---

### Task 2: Persisted Session, Step, and Verification State

**Files:**
- Modify: `src/learnlab/state.py`
- Modify: `tests/test_state.py`

**Interfaces:**
- Produces: `StepStatus`, `VerificationStatus`, `CompletionSource`, `SessionCursor`, `VerificationRecord`.
- Methods: `session_cursor`, `set_session_cursor`, `step_statuses`, `start_step`, `record_verification_result`, `verification_records`, `complete_step`, `complete_lesson_validated`, and enriched `complete_lesson(..., source)`.

- [ ] **Step 1: Write a failing additive migration test**

Create a database at the current schema, seed completed/in-progress lesson rows and an owned environment, run new `initialize()`, and assert new tables/columns exist while every prior row is unchanged. Assert completed legacy lessons return `CompletionSource.LEGACY` and no invented evidence rows.

- [ ] **Step 2: Run migration test and verify RED**

Run: `python3.13 -m pytest tests/test_state.py -k session_migration -q`

Expected: missing tables or repository types.

- [ ] **Step 3: Implement transactional additive schema migration**

Add `session_cursors`, `step_progress`, and `verification_progress`. Keys include collection/course/lesson/step/verification. Use checked status/type/self-attested fields, bounded evidence enforced before repository call, attempt count, and UTC timestamps. Add `completion_source` to progress via safe column migration. Migration stays under the existing atomic schema transaction and does not weaken retired legacy DB triggers.

- [ ] **Step 4: Write failing state-transition tests**

```python
def test_failed_verification_increments_attempt_without_completing_step(store):
    store.start_step(PATH)
    store.record_verification_result(PATH, "check-os", passed=False, evidence="bad")
    [record] = store.verification_records(PATH)
    assert record.status is VerificationStatus.FAILED
    assert record.attempt_count == 1
    assert store.step_statuses(COURSE_PATH)["inspect"] is StepStatus.IN_PROGRESS


def test_all_verifications_complete_step_and_lesson_transactionally(store):
    seed_two_verifications(store)
    store.complete_step(PATH)
    assert store.step_statuses(COURSE_PATH)["inspect"] is StepStatus.COMPLETED
    store.complete_lesson_validated(LESSON_PATH)
    assert store.lesson_completion_source(LESSON_PATH) is CompletionSource.VALIDATED
```

Cover retry preserving prior passed checks, cursor persistence, self-attested flag, 8 KiB evidence rejection, reset deletion, destroy preserve-progress retention of completed step/check rows, destroy erase removal, and manual override provenance.

- [ ] **Step 5: Implement repository methods and verify GREEN**

Every state transition is one explicit transaction. `complete_step` verifies all expected verification IDs passed; caller supplies the curriculum IDs to prevent removed checks being silently ignored. `complete_lesson_validated` similarly verifies all expected steps.

Run: `python3.13 -m pytest tests/test_state.py -q && python3.13 -m pytest -m 'not live' -q`

- [ ] **Step 6: Commit**

```bash
git add src/learnlab/state.py tests/test_state.py
git commit -m "feat: persist interactive verification progress"
```

---

### Task 3: Structured Lifecycle Progress Events

**Files:**
- Create: `src/learnlab/progress.py`
- Modify: `src/learnlab/lifecycle.py`
- Modify: `src/learnlab/providers/base.py`
- Modify: `src/learnlab/providers/proxmox.py`
- Create: `tests/test_progress.py`
- Modify: `tests/test_lifecycle.py`
- Modify: `tests/providers/test_proxmox.py`

**Interfaces:**
- Produces: `ProgressKind`, `ProgressEvent`, `ProgressObserver`, `NullProgressObserver`.
- `LifecycleService(..., progress: ProgressObserver = NullProgressObserver())`.
- Polling methods accept an optional heartbeat callback without changing provider outcomes.

- [ ] **Step 1: Write failing lifecycle event-order test**

```python
def test_start_emits_immediate_ordered_safe_progress(store, provider, recorder):
    LifecycleService(store, provider, tmp_path, progress=recorder).start(request)
    assert recorder.kinds == [
        "environment-requested", "allocating-vmid", "clone-requested",
        "clone-waiting", "clone-complete", "start-requested", "start-waiting",
        "guest-agent-waiting", "address-discovery", "environment-ready",
    ]
    assert recorder.events[0].elapsed_seconds == 0
    assert all("secret" not in event.message for event in recorder.events)
```

- [ ] **Step 2: Verify RED and implement immutable event types**

Run: `python3.13 -m pytest tests/test_progress.py tests/test_lifecycle.py -k progress -q`

Events validate nonnegative elapsed time and optional positive attempt. Observer exceptions are caught, redacted, and ignored so UI failure cannot change infrastructure state.

- [ ] **Step 3: Add failing unchanged-state heartbeat tests**

With fake monotonic time, queue multiple running task responses and guest-agent retries. Assert heartbeat attempts increment and occur at the provider's existing poll interval without extending deadlines.

- [ ] **Step 4: Implement heartbeat callbacks and lifecycle mapping**

Keep provider protocol UI-neutral: callbacks receive attempt only; lifecycle maps them to safe events. Emit the first event before provider/profile access. Never include UPIDs, raw responses, or authorization.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python3.13 -m pytest tests/test_progress.py tests/test_lifecycle.py tests/providers/test_proxmox.py -q && python3.13 -m pytest -m 'not live' -q`

```bash
git add src/learnlab/progress.py src/learnlab/lifecycle.py \
  src/learnlab/providers/base.py src/learnlab/providers/proxmox.py \
  tests/test_progress.py tests/test_lifecycle.py tests/providers/test_proxmox.py
git commit -m "feat: emit lifecycle progress events"
```

---

### Task 4: Strict SSH Remote Command Executor

**Files:**
- Modify: `src/learnlab/ssh.py`
- Create: `tests/test_ssh.py`

**Interfaces:**
- Produces: `RemoteCommandResult`, `SshCommandTimeout`, and `SshExecutor.run(profile, environment, command, timeout) -> RemoteCommandResult`.
- Constructor accepts injectable `runner` for offline tests; production uses `subprocess.run` without a local shell.

- [ ] **Step 1: Write failing command-shape tests**

Assert argv includes identity, `BatchMode=yes`, `StrictHostKeyChecking=yes`, isolated `UserKnownHostsFile`, connect timeout, `user@ip`, and the curriculum command as one final argv element. Assert `shell` is never true and normal `~/.ssh/known_hosts` is absent.

- [ ] **Step 2: Verify RED and implement executor**

Run: `python3.13 -m pytest tests/test_ssh.py -q`

Use `subprocess.run(argv, capture_output=True, text=False, timeout=..., check=False)`. Bound stdout/stderr to 8 KiB each after decoding with replacement. Map timeout separately and redact configured secrets supplied to the executor.

- [ ] **Step 3: Add timeout/output/redaction/exit tests**

Cover exit zero/nonzero, binary decoding, oversized output, command string containing shell metacharacters remaining one remote argument, subprocess timeout, and secret removal.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python3.13 -m pytest tests/test_ssh.py -q && python3.13 -m ruff check src/learnlab/ssh.py tests/test_ssh.py && python3.13 -m mypy src/learnlab/ssh.py`

```bash
git add src/learnlab/ssh.py tests/test_ssh.py
git commit -m "feat: execute strict remote verification commands"
```

---

### Task 5: Validator Registry and Four Validator Types

**Files:**
- Create: `src/learnlab/validation.py`
- Modify: `src/learnlab/providers/base.py`
- Modify: `src/learnlab/providers/proxmox.py`
- Create: `tests/test_validation.py`
- Modify: `tests/providers/test_proxmox.py`

**Interfaces:**
- Produces: `ValidationContext`, `VerificationResult`, `Validator` protocol, `ValidatorRegistry`, and four validators.
- Adds `Provider.run_check(check: str, environment: EnvironmentRecord | None) -> ProviderCheck` with named read-only Proxmox checks.

- [ ] **Step 1: Write failing remote/text/manual validator tests**

Remote passes only on exit zero and reports bounded safe output on failure. Text exact trims outer whitespace; regex searches bounded evidence; oversize rejects before persistence. Manual uses injected prompt, yes returns `passed=True, self_attested=True`, no returns failed/incomplete.

- [ ] **Step 2: Verify RED and implement common result/registry**

Run: `python3.13 -m pytest tests/test_validation.py -q`

Registry rejects duplicate registrations and unknown types. Result evidence is capped at 8 KiB and summary at 500 characters.

- [ ] **Step 3: Write failing provider-check contract tests**

Test `api-reachable`, `template-visible`, `vm-running`, and `guest-agent-ready`; assert only GET or proven read-only ping operation occurs, environment-required checks reject missing environment, and no mutation method/path is called.

- [ ] **Step 4: Implement provider-check dispatch**

Reuse health/config/location primitives. `guest-agent-ready` uses the existing agent ping but never waits indefinitely or changes state. Unknown check is a curriculum/programming error.

- [ ] **Step 5: Add repeated/all-required orchestration helper test**

`validate_step` runs ordered items, skips already passed IDs, stops on first failure, and returns the next incomplete ID. It does not mark state itself; session service owns persistence.

- [ ] **Step 6: Verify GREEN and commit**

Run: `python3.13 -m pytest tests/test_validation.py tests/providers/test_proxmox.py -q && python3.13 -m pytest -m 'not live' -q`

```bash
git add src/learnlab/validation.py src/learnlab/providers/base.py \
  src/learnlab/providers/proxmox.py tests/test_validation.py \
  tests/providers/test_proxmox.py
git commit -m "feat: add typed lesson validators"
```

---

### Task 6: Environment Scope Orchestration

**Files:**
- Modify: `src/learnlab/lifecycle.py`
- Modify: `src/learnlab/state.py`
- Modify: `tests/test_lifecycle.py`
- Modify: `tests/test_state.py`

**Interfaces:**
- Produces: `EnvironmentResolution` and `LifecycleService.ensure_environment(request, policy, replace_confirmed=False)`.
- Adds focused `destroy_environment(confirmed_record)` reusing existing ownership-safe teardown; global destroy remains unchanged.

- [ ] **Step 1: Write failing `none` and course-reuse tests**

`none` returns no environment with zero provider calls. `course` creates once, then returns the existing record without allocate/clone/start after fingerprint/name/location ownership reconciliation.

- [ ] **Step 2: Verify RED and implement policy resolution**

Run: `python3.13 -m pytest tests/test_lifecycle.py -k 'environment_scope' -q`

Persist effective scope and lesson owner additively on environment/attempt records. Reuse requires recorded/current fingerprint, endpoint, VMID, expected name, and actual name match.

- [ ] **Step 3: Write failing lesson replacement tests**

An existing environment for the same lesson reuses. A different lesson returns `replacement_required` without mutation. With explicit confirmation, stop/delete/verify old first, then create new. Failure/cancellation keeps old state and makes no allocation call.

- [ ] **Step 4: Implement focused replacement using safe teardown**

Do not call global progress erasure. Delete only the confirmed environment record/directory after remote absence. Retain clone uncertainty and ownership safety unchanged.

- [ ] **Step 5: Add external-disappearance and override tests**

Course environment missing remotely produces a safe resolution requiring explicit recreation; never bind a same-VMID wrong name. Lesson `none` override leaves a recorded course environment untouched for later lessons.

- [ ] **Step 6: Verify GREEN and commit**

Run: `python3.13 -m pytest tests/test_lifecycle.py tests/test_state.py -q && python3.13 -m pytest -m 'not live' -q`

```bash
git add src/learnlab/lifecycle.py src/learnlab/state.py tests/test_lifecycle.py tests/test_state.py
git commit -m "feat: apply curriculum environment scopes"
```

---

### Task 7: Provider-Neutral Interactive Session State Machine

**Files:**
- Create: `src/learnlab/session.py`
- Create: `tests/test_session.py`

**Interfaces:**
- Produces: `CourseSession`, `SessionAction`, `SessionPrompt` protocol, `SessionOutcome`.
- Consumes curriculum, state, lifecycle, validator registry, provider/profile, and prompt adapter; emits no Typer output.

- [ ] **Step 1: Write failing first-incomplete/resume test**

Seed first check passed and second failed. Start session and assert it presents only the second verification, then persists its passing result before moving forward.

- [ ] **Step 2: Verify RED and implement one-step loop**

Run: `python3.13 -m pytest tests/test_session.py -q`

Session cursor is persisted before prompt and after each result. Save-and-exit returns without changing incomplete status or environment.

- [ ] **Step 3: Add retry and all-required tests**

Failure presents safe guidance and choices retry/save. Passing retry increments attempts, preserves earlier passed checks, completes step only after all pass, then moves to next step.

- [ ] **Step 4: Add lesson completion and next-lesson tests**

Completing final step marks validated lesson completion and offers continue/review/exit. Continue chooses first incomplete next lesson. Course scope reuses; lesson scope requests replacement confirmation; none scope avoids provider.

- [ ] **Step 5: Add interruption and legacy completion tests**

Injected interrupt returns saved outcome with current cursor. Legacy completed lesson is labeled and skipped unless explicitly reviewed. Provider/SSH/state failure contains course/lesson/step/check context and no secret.

- [ ] **Step 6: Verify GREEN and commit**

Run: `python3.13 -m pytest tests/test_session.py -q && python3.13 -m pytest -m 'not live' -q`

```bash
git add src/learnlab/session.py tests/test_session.py
git commit -m "feat: run resumable interactive course sessions"
```

---

### Task 8: CLI Progress Renderer, `start`, and `resume`

**Files:**
- Modify: `src/learnlab/cli.py`
- Create: `tests/test_cli_progress.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Adds: `learnlab resume <collection>/<course> [--provider PROFILE]`.
- `start` and `resume` share `_run_course_session`.
- Produces `TerminalProgressRenderer` implementing `ProgressObserver` and a Typer prompt adapter implementing `SessionPrompt`.

- [ ] **Step 1: Write failing immediate life-sign test**

Use a lifecycle fake that blocks on an event. Invoke CLI in a worker and assert `Creating lesson environment` is written before releasing the fake. This proves output precedes provisioning completion.

- [ ] **Step 2: Write failing TTY/non-TTY renderer tests**

TTY output updates one spinner line with elapsed time; non-TTY emits deterministic stage lines and heartbeat attempts. Renderer closes cleanly on success/error/interrupt. Inject clock and terminal capability—no sleeps.

- [ ] **Step 3: Implement renderer and shared course runner**

Print selected course/lesson and environment policy before provisioning. Construct provider only when effective scope requires it. Wire lifecycle progress and session prompts without placing lifecycle logic in CLI.

- [ ] **Step 4: Add start/resume behavior tests**

Start resumes existing progress/environment instead of conflict. Resume without state exits 2 with `use learnlab start`. Existing matching course environment is reused; lesson replacement lists target and confirms; none scope loads without config/secret.

- [ ] **Step 5: Add interactive verification output tests**

Assert one step/check at a time, failed guidance/retry, self-attested label, next-lesson offer, save-and-exit, and no return to shell until outcome. Verify secrets absent.

- [ ] **Step 6: Verify GREEN and commit**

Run: `python3.13 -m pytest tests/test_cli.py tests/test_cli_progress.py -q && python3.13 -m pytest -m 'not live' -q`

```bash
git add src/learnlab/cli.py tests/test_cli.py tests/test_cli_progress.py
git commit -m "feat: add interactive start and resume commands"
```

---

### Task 9: Manual Override, Curriculum Content, Packaging, and Documentation

**Files:**
- Modify: `src/learnlab/cli.py`
- Modify: `collections/proxmox/courses/proxmox-admin/course.yaml`
- Modify: both lesson YAML files under `collections/proxmox/...`
- Modify: packaged mirror under `src/learnlab/collections/proxmox/...`
- Modify: `README.md`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_packaging.py`

**Interfaces:**
- Manual completion requires confirmation and records `CompletionSource.MANUAL_OVERRIDE`.
- Authoring and packaged curriculum trees must be byte-identical.

- [ ] **Step 1: Write failing manual override confirmation test**

Cancellation leaves progress unchanged. Confirmation prints that normal learners should use start/resume and persists manual provenance. `--yes` is supported for deliberate scripts.

- [ ] **Step 2: Update Proxmox curriculum with approved schema**

Choose and document an explicit scope. Include examples exercising repeated validators without requiring dangerous provider mutations. Conceptual steps use text/manual/provider checks as appropriate; do not include secrets or deployment values.

- [ ] **Step 3: Add authoring/package equality and wheel tests**

Recursively compare relative paths and bytes. Build wheel offline, install/extract it, load course through `importlib.resources`, and assert scope plus verification order/types.

- [ ] **Step 4: Update README**

Document environment scopes, interactive start/resume, progress display, verification types/all-required semantics, save/exit/resume, manual override provenance, lesson replacement confirmation, and strict SSH/provider safety.

- [ ] **Step 5: Verify and commit**

Run: `python3.13 -m pytest tests/test_cli.py tests/test_packaging.py tests/test_curriculum.py -q && python3.13 -m pytest -m 'not live' -q`

```bash
git add src/learnlab/cli.py README.md \
  collections/proxmox/courses/proxmox-admin/course.yaml \
  collections/proxmox/courses/proxmox-admin/lessons \
  src/learnlab/collections/proxmox/courses/proxmox-admin/course.yaml \
  src/learnlab/collections/proxmox/courses/proxmox-admin/lessons \
  tests/test_cli.py tests/test_packaging.py
git commit -m "docs: ship interactive Proxmox curriculum"
```

---

### Task 10: Full Integration and Final Quality Gate

**Files:**
- Create: `tests/test_interactive_course_integration.py`
- Modify only a production file implicated by a reproducing failure, after adding
  the smallest failing regression test to its owning test module.

**Interfaces:**
- Verifies the complete public workflow without live infrastructure.

- [ ] **Step 1: Add full fake-course integration test**

From isolated XDG roots, invoke registered Typer app to: start a course; observe immediate non-TTY progress; create one fake course environment; fail then pass repeated verifications; save; resume at the incomplete check; complete lesson; continue to lesson two reusing the same VM; then destroy preserving validated progress. Assert provider operation order, SQLite state, `0600` known_hosts, and no secret output.

- [ ] **Step 2: Add lesson/none-scope integration tests**

Lesson scope must confirm and destroy old ownership-safe VM before new allocation. None scope completes without loading provider settings. Cancellation and ownership mismatch make zero destructive calls.

- [ ] **Step 3: Run fresh complete evidence gate**

```bash
python3.13 -m pytest -m 'not live' -q
python3.13 -m pytest tests/live -q
python3.13 -m ruff check src tests
python3.13 -m ruff format --check src tests
python3.13 -m mypy src
python3.13 -m pytest tests/test_packaging.py -q
git diff --check
git status --short
```

Expected: offline suite passes, live suite skips, all static/packaging checks pass, and status contains only intentional final changes.

- [ ] **Step 4: Commit only test-backed corrections**

If the gate required semantic changes, retain their RED/GREEN evidence and commit them with a behavior-specific message. Mechanical formatting may be applied after tests are green. Do not create an empty commit.
