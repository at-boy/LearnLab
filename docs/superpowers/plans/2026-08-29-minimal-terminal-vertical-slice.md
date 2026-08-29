# Minimal Terminal-First Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a Python 3.13 CLI that tests named Proxmox profiles, starts an ordered LearnLab course in a disposable NixOS VM, persists local progress, and safely resets or destroys state.

**Architecture:** A thin Typer CLI coordinates a YAML curriculum catalog, a transactional SQLite state store, a provider-neutral lifecycle service, and a synchronous HTTPX Proxmox adapter. Provider configuration is per-user TOML, secrets are read only from named environment variables, and every disposable environment receives its own SSH `known_hosts` file.

**Tech Stack:** Python 3.13, hatchling, Typer, HTTPX, PyYAML, platformdirs, SQLite (`sqlite3`), pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-29-minimal-terminal-vertical-slice-design.md`

## Global Constraints

- Runtime is Python 3.13 on Debian 13.
- Preserve `Platform > Collection > Course > Lesson > Steps` with explicit YAML ordering.
- Provider infrastructure values live only in named per-user profiles; curriculum cannot contain VMIDs, node, storage, network, API URL, profile name, or credentials.
- Token secret values are read from the configured environment variable and never stored, logged, serialized, or included in exceptions.
- Proxmox uses `GET` VM config; `POST` clone/start/stop/agent ping; `GET` guest network interfaces; and `DELETE` VM.
- Every asynchronous UPID operation must reach `status == "stopped"` and `exitstatus == "OK"`.
- Every environment uses its own `known_hosts`; never alter the user's normal SSH host-key database.
- All production behavior follows red-green-refactor with an observed failing test before implementation.
- Normal tests are offline; the real Proxmox acceptance test is separately marked and explicitly opted in.

## File Map

```text
pyproject.toml                         package metadata, dependencies, tools, CLI entry point
README.md                              install/configure/use instructions and safety notes
src/learnlab/__init__.py               package version
src/learnlab/cli.py                    Typer commands and prompting only
src/learnlab/config.py                 XDG paths, TOML profiles, environment-secret lookup
src/learnlab/errors.py                 typed public errors and secret-safe rendering
src/learnlab/curriculum.py             YAML models, validation, catalog and ordering
src/learnlab/state.py                  SQLite schema and transactional state repository
src/learnlab/providers/base.py         provider protocol and provider-neutral result models
src/learnlab/providers/proxmox.py      exact Proxmox HTTP contract and UPID polling
src/learnlab/providers/registry.py     named-profile-to-provider construction
src/learnlab/lifecycle.py              start/reset/destroy use cases
src/learnlab/ssh.py                    isolated known_hosts creation and SSH command rendering
collections/proxmox/...                minimal teachable Proxmox collection/course/lesson
tests/conftest.py                      reusable temporary XDG and fake-provider fixtures
tests/test_config.py                   profile, secret and redaction behavior
tests/test_curriculum.py               hierarchy and explicit ordering
tests/test_state.py                    SQLite transitions, progress and reset scope
tests/providers/test_proxmox.py        exact HTTP method/path and polling contracts
tests/test_lifecycle.py                provider-neutral orchestration and failure recovery
tests/test_cli.py                      terminal behavior and confirmation rules
tests/live/test_proxmox_lifecycle.py   opt-in real Checkpoint 05 acceptance lifecycle
```

---

### Task 1: Package Skeleton, Configuration, and Secret Safety

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/learnlab/__init__.py`
- Create: `src/learnlab/config.py`
- Create: `src/learnlab/errors.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `ProxmoxProfile`, `Settings`, `config_path()`, `state_dir()`, `load_settings()`, `resolve_token_secret(profile)`, `LearnLabError`, `ConfigurationError`, and `redact(text, secrets)`.
- `ProxmoxProfile` fields: `name`, `api_url`, `token_id`, `token_secret_env`, `template_vmid`, `template_name`, `node`, `storage`, `network`, `ssh_user`, `ssh_identity_file`, `tls_verify`.

- [ ] **Step 1: Add package/tool metadata and ignore local state**

Create `pyproject.toml` with `requires-python = ">=3.13"`, hatchling build backend, `src` layout, and dependencies `typer>=0.16,<1`, `httpx>=0.28,<1`, `PyYAML>=6.0,<7`, and `platformdirs>=4.3,<5`. Add a `learnlab = "learnlab.cli:app"` script. Add pytest, Ruff, and mypy under a `dev` optional dependency, configure pytest with `testpaths = ["tests"]` and markers `live`, and enable Ruff rules `E`, `F`, `I`, `B`, `UP`, and `S` while allowing `S101` in tests.

Create `.gitignore` containing:

```gitignore
.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.pyc
*.db
.coverage
```

- [ ] **Step 2: Write failing named-profile and missing-secret tests**

```python
def test_loads_named_proxmox_profile(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")
    settings = load_settings(config)
    profile = settings.provider("home-proxmox")
    assert settings.default_provider == "home-proxmox"
    assert profile.template_vmid == 9001
    assert profile.tls_verify is True


def test_secret_is_resolved_only_from_named_environment(monkeypatch):
    profile = profile_fixture(token_secret_env="LEARNLAB_TEST_SECRET")
    monkeypatch.setenv("LEARNLAB_TEST_SECRET", "private-value")
    assert resolve_token_secret(profile) == "private-value"
    assert "private-value" not in repr(profile)


def test_missing_secret_names_variable_without_disclosing_values(monkeypatch):
    profile = profile_fixture(token_secret_env="LEARNLAB_TEST_SECRET")
    monkeypatch.delenv("LEARNLAB_TEST_SECRET", raising=False)
    with pytest.raises(ConfigurationError, match="LEARNLAB_TEST_SECRET"):
        resolve_token_secret(profile)
```

The `CONFIG` fixture must include every profile field from the approved spec plus `ssh_user = "student"` and `ssh_identity_file = "~/.ssh/learning-platform"`.

- [ ] **Step 3: Run the focused test and verify RED**

Run: `python3.13 -m pytest tests/test_config.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'learnlab'`.

- [ ] **Step 4: Implement immutable configuration models and XDG paths**

Use frozen dataclasses. Parse with `tomllib`, require the exact profile keys, reject unknown provider types, validate positive VMID and an `https://` API URL, expand only the SSH identity path, and never store the resolved secret on the dataclass. `Settings.provider(name)` raises `ConfigurationError("Unknown provider profile: <name>")`.

`config_path()` uses `PlatformDirs("learnlab").user_config_path / "config.toml"`; `state_dir()` uses `PlatformDirs("learnlab").user_state_path`. Both accept explicit paths at higher-level call sites for tests.

- [ ] **Step 5: Add redaction tests and implementation**

```python
def test_redact_replaces_each_nonempty_secret():
    text = "Authorization: PVEAPIToken=id=private-value"
    assert redact(text, {"private-value"}) == "Authorization: PVEAPIToken=id=[REDACTED]"
```

`redact` ignores empty strings, sorts secrets longest-first, and replaces exact occurrences with `[REDACTED]`. Public error classes contain operation context but never accept an HTTPX request object whose headers could expose authorization.

- [ ] **Step 6: Verify GREEN and static quality**

Run: `python3.13 -m pytest tests/test_config.py -q && python3.13 -m ruff check src tests && python3.13 -m mypy src`

Expected: all commands pass.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore src/learnlab tests/conftest.py tests/test_config.py
git commit -m "feat: add named provider configuration"
```

---

### Task 2: Proxmox HTTP Contract and Task Polling

**Files:**
- Create: `src/learnlab/providers/__init__.py`
- Create: `src/learnlab/providers/base.py`
- Create: `src/learnlab/providers/proxmox.py`
- Create: `tests/providers/test_proxmox.py`
- Create: `tests/providers/fake_proxmox.py`

**Interfaces:**
- Produces: `ProviderHealth`, `VmLocation`, `Provider` protocol, `ProxmoxProvider`.
- `ProxmoxProvider` methods: `health_check() -> ProviderHealth`, `allocate_vmid() -> int`, `clone(vmid: int, name: str) -> str`, `wait_for_task(node: str, upid: str, timeout: float) -> None`, `locate_vm(vmid: int) -> VmLocation | None`, `start(vmid: int, node: str) -> str`, `stop(vmid: int, node: str) -> str`, `wait_for_ipv4(vmid: int, node: str, timeout: float) -> str`, and `delete(vmid: int, node: str) -> str`.
- Consumes: `ProxmoxProfile`, token secret string, injectable `httpx.Client`, `clock: Callable[[], float]`, and `sleep: Callable[[float], None]`.

- [ ] **Step 1: Write the fake server recorder and failing method/path tests**

Use `ThreadingHTTPServer` on `127.0.0.1` with a handler that appends `(method, path, body, authorization)` to a thread-safe list and pops queued JSON responses. The fixture shuts down and joins the server in `finally`.

```python
def test_clone_uses_post_and_expected_form(fake_server, profile):
    fake_server.queue(200, {"data": "UPID:pve02:clone:"})
    provider = provider_for(fake_server, profile)
    upid = provider.clone(102, "learnlab-102")
    request = fake_server.requests.one()
    assert request.method == "POST"
    assert request.path == "/api2/json/nodes/pve02/qemu/9001/clone"
    assert parse_qs(request.body) == {
        "newid": ["102"], "name": ["learnlab-102"], "full": ["1"],
        "storage": ["local-lvm"],
    }
    assert upid == "UPID:pve02:clone:"


@pytest.mark.parametrize((operation, method, path), [
    ("start", "POST", "/api2/json/nodes/pve02/qemu/102/status/start"),
    ("stop", "POST", "/api2/json/nodes/pve02/qemu/102/status/stop"),
    ("delete", "DELETE", "/api2/json/nodes/pve02/qemu/102"),
])
def test_mutating_methods_are_explicit(operation, method, path, fake_server, profile):
    fake_server.queue(200, {"data": "UPID:pve02:task:"})
    result = getattr(provider_for(fake_server, profile), operation)(102, "pve02")
    assert fake_server.requests.one().method == method
    assert fake_server.requests.one().path == path
    assert result == "UPID:pve02:task:"
```

- [ ] **Step 2: Run provider tests and verify RED**

Run: `python3.13 -m pytest tests/providers/test_proxmox.py -q`

Expected: collection fails because `learnlab.providers.proxmox` does not exist.

- [ ] **Step 3: Implement request envelope handling and explicit primitives**

Build the authorization header exactly as `PVEAPIToken=<token_id>=<secret>`. Use `httpx.Client(base_url=f"{api_url.rstrip('/')}/api2/json", verify=tls_verify, timeout=10.0)`. A private `_request(method, path, data=None)` validates HTTP success, parses the JSON `data` envelope, bounds error bodies to 2,000 characters, redacts the secret, and raises typed `ProviderAuthenticationError`, `ProviderAuthorizationError`, or `ProviderOperationError` without retaining request headers.

Use `urllib.parse.quote(upid, safe="")` for task paths. Do not infer verbs from endpoint shapes.

- [ ] **Step 4: Write failing UPID completion, failure, and timeout tests**

```python
def test_wait_for_task_requires_stopped_and_ok(fake_server, provider):
    fake_server.queue(200, {"data": {"status": "running"}})
    fake_server.queue(200, {"data": {"status": "stopped", "exitstatus": "OK"}})
    provider.wait_for_task("pve02", "UPID:pve02:a/b!:", timeout=5)
    assert fake_server.requests.last().path.endswith("UPID%3Apve02%3Aa%2Fb%21%3A/status")


def test_wait_for_task_rejects_non_ok_exit(fake_server, provider):
    fake_server.queue(200, {"data": {"status": "stopped", "exitstatus": "ERROR"}})
    with pytest.raises(ProviderTaskFailed, match="ERROR"):
        provider.wait_for_task("pve02", "UPID:pve02:bad:", timeout=5)


def test_wait_for_task_times_out_with_operation_context(fake_server, provider):
    fake_server.always(200, {"data": {"status": "running"}})
    with pytest.raises(ProviderTimeoutError, match="UPID"):
        provider.wait_for_task("pve02", "UPID:pve02:slow:", timeout=2)
```

Use a fake monotonic clock advanced by the injected `sleep` so tests never wait in real time.

- [ ] **Step 5: Implement strict task polling and guest network discovery**

Poll once immediately and then every two injected seconds. Treat only `stopped` as terminal and require `exitstatus == "OK"`.

For `wait_for_ipv4`, retry `POST .../agent/ping` until it succeeds, then retry `GET .../agent/network-get-interfaces`. Select the first address whose type is `ipv4` and value is not loopback according to `ipaddress.ip_address(address).is_loopback`. Invalid addresses are ignored. A bounded timeout raises `ProviderTimeoutError("Timed out waiting for guest IPv4 for VM <vmid>")`.

- [ ] **Step 6: Write and pass the read-only health-check contract test**

Queue `/version`, `/nodes`, `/cluster/resources?type=vm`, and configured VM config responses. Assert `health_check()` returns individual named checks for API, authentication, node, template identity, storage, and network, with an informational warning that scoped mutation permissions including `SDN.Use` are not proven. Assert no request uses `POST`, `PUT`, or `DELETE`.

- [ ] **Step 7: Verify GREEN**

Run: `python3.13 -m pytest tests/providers/test_proxmox.py -q && python3.13 -m pytest -q && python3.13 -m ruff check src tests && python3.13 -m mypy src`

Expected: all commands pass.

- [ ] **Step 8: Commit**

```bash
git add src/learnlab/providers tests/providers
git commit -m "feat: implement Proxmox provider contract"
```

---

### Task 3: Provider Registry and `provider test` CLI

**Files:**
- Create: `src/learnlab/providers/registry.py`
- Create: `src/learnlab/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Produces: `build_provider(settings, profile_name, client=None) -> Provider` and Typer `app`.
- Consumes: configuration and `ProxmoxProvider.health_check()`.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_provider_test_uses_named_profile(monkeypatch, tmp_xdg, fake_health_provider):
    monkeypatch.setenv("LEARNLAB_HOME_SECRET", "secret")
    result = runner.invoke(app, ["provider", "test", "home-proxmox"])
    assert result.exit_code == 0
    assert "home-proxmox" in result.stdout
    assert "Template identity" in result.stdout
    assert "SDN.Use" in result.stdout
    assert "secret" not in result.stdout


def test_provider_test_unknown_profile_is_actionable(tmp_xdg):
    result = runner.invoke(app, ["provider", "test", "missing"])
    assert result.exit_code == 2
    assert "Unknown provider profile: missing" in result.stdout
```

Inject registry construction through `app.state.provider_factory` or an equivalent explicit dependency hook; do not monkeypatch HTTPX internals.

- [ ] **Step 2: Run tests and verify RED**

Run: `python3.13 -m pytest tests/test_cli.py -q`

Expected: import fails because `learnlab.cli` does not exist.

- [ ] **Step 3: Implement the provider command group**

Use a Typer root app with a `provider` sub-app. Render one line per `ProviderHealth` check and use exit code `1` when any required check fails, `2` for local input/configuration errors, and `3` for provider/network errors. Emit a visible TLS warning when `tls_verify` is false. Catch only `LearnLabError` at the CLI boundary and render its safe message.

- [ ] **Step 4: Verify installed entry point and full suite**

Run: `python3.13 -m pip install -e '.[dev]' && learnlab --help && python3.13 -m pytest -q`

Expected: help lists `provider`; all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/learnlab/cli.py src/learnlab/providers/registry.py tests/test_cli.py
git commit -m "feat: add provider health-check command"
```

---

### Task 4: Curriculum Hierarchy and Minimal Proxmox Course

**Files:**
- Create: `src/learnlab/curriculum.py`
- Create: `collections/proxmox/collection.yaml`
- Create: `collections/proxmox/courses/proxmox-admin/course.yaml`
- Create: `collections/proxmox/courses/proxmox-admin/lessons/00-api-access/lesson.yaml`
- Create: `collections/proxmox/courses/proxmox-admin/lessons/01-api-tokens/lesson.yaml`
- Create: `tests/test_curriculum.py`

**Interfaces:**
- Produces frozen `Step`, `Lesson`, `Course`, `Collection`, and `CurriculumCatalog`.
- `CurriculumCatalog.load_course("proxmox/proxmox-admin") -> Course`; `Course.lessons` is ordered; `Course.first_incomplete(completed_ids) -> Lesson`.

- [ ] **Step 1: Write failing hierarchy and ordering tests**

```python
def test_loads_explicit_platform_hierarchy(collections_dir):
    course = CurriculumCatalog(collections_dir).load_course("proxmox/proxmox-admin")
    assert course.collection_id == "proxmox"
    assert course.id == "proxmox-admin"
    assert [lesson.id for lesson in course.lessons] == ["api-access", "api-tokens"]
    assert [step.id for step in course.lessons[0].steps] == ["understand-api", "locate-endpoint"]


def test_first_incomplete_follows_course_order(course):
    assert course.first_incomplete({"api-access"}).id == "api-tokens"


@pytest.mark.parametrize("invalid_path", ["proxmox", "a/b/c", "/proxmox-admin"])
def test_course_path_requires_collection_slash_course(invalid_path, collections_dir):
    with pytest.raises(CurriculumError, match="collection/course"):
        CurriculumCatalog(collections_dir).load_course(invalid_path)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3.13 -m pytest tests/test_curriculum.py -q`

Expected: collection fails because `learnlab.curriculum` does not exist.

- [ ] **Step 3: Implement strict YAML models and loader**

Use `yaml.safe_load`. Require mapping roots, stable IDs, nonempty titles, explicit course `lessons` list, and explicit lesson `steps` list. Reject duplicate lesson and step IDs, missing lesson directories, ID/path mismatches, and unknown object keys with `CurriculumError` containing the source path. Keep provider deployment fields out of curriculum models.

- [ ] **Step 4: Author minimal teachable content**

`collection.yaml` identifies `proxmox`; `course.yaml` identifies `proxmox-admin`, lists `api-access` then `api-tokens`, and declares no deployment profile. The two lesson files explain API concepts and dedicated token identity at a safe conceptual level. Each has at least two ordered steps. Do not include any real API endpoint hostname, token secret, VMID, node, storage, or network value.

- [ ] **Step 5: Add a security regression test for curriculum**

Recursively load YAML text and assert it contains none of `token_secret`, `PVEAPIToken=`, or the configured secret fixture. Also assert the parsed YAML has no keys `template_vmid`, `node`, `storage`, `network`, `api_url`, or `provider_profile`.

- [ ] **Step 6: Verify GREEN and commit**

Run: `python3.13 -m pytest tests/test_curriculum.py -q && python3.13 -m pytest -q`

```bash
git add src/learnlab/curriculum.py collections tests/test_curriculum.py
git commit -m "feat: add ordered curriculum hierarchy"
```

---

### Task 5: Transactional Progress and Environment State

**Files:**
- Create: `src/learnlab/state.py`
- Create: `tests/test_state.py`

**Interfaces:**
- Produces: `StateStore(db_path)`, `ProgressStatus`, `EnvironmentPhase`, `EnvironmentRecord`.
- Key methods: `initialize()`, `completed_lessons(collection, course)`, `mark_lesson(collection, course, lesson, status)`, `create_attempt(...)`, `create_environment(...)`, `transition_environment(id, phase, **fields)`, `active_environment(collection, course)`, `list_environments()`, `delete_environment(id)`, `reset_scope(collection, course=None)`, `erase_all(preserve_completed: bool)`.

- [ ] **Step 1: Write failing schema and persistence tests**

```python
def test_progress_persists_between_store_instances(tmp_path):
    path = tmp_path / "learnlab.db"
    first = StateStore(path)
    first.initialize()
    first.mark_lesson("proxmox", "proxmox-admin", "api-access", ProgressStatus.COMPLETED)
    second = StateStore(path)
    second.initialize()
    assert second.completed_lessons("proxmox", "proxmox-admin") == {"api-access"}


def test_only_one_active_environment_per_course(store):
    store.create_environment(environment_fixture(id="one"))
    with pytest.raises(StateConflictError, match="active environment"):
        store.create_environment(environment_fixture(id="two"))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3.13 -m pytest tests/test_state.py -q`

Expected: collection fails because `learnlab.state` does not exist.

- [ ] **Step 3: Implement schema and transactional repository**

Create tables `progress`, `attempts`, and `environments`; enable `PRAGMA foreign_keys = ON`; use WAL mode; store enum values as checked text. Add a partial unique index over `(collection_id, course_id)` for all retained environment records. Use UTC ISO-8601 timestamps. Every public write opens `with connection:` and either commits completely or rolls back.

Environment columns include `id`, course/lesson/attempt IDs, profile, provider type, VMID, node, IP, phase, UPID, safe error summary, and timestamps. There is no credential column.

- [ ] **Step 4: Write failing transition and reset-scope tests**

```python
def test_transition_records_each_remote_boundary(store):
    store.create_environment(environment_fixture(phase=EnvironmentPhase.ALLOCATING))
    store.transition_environment("env-1", EnvironmentPhase.CLONING, vmid=102, upid="UPID:clone")
    record = store.get_environment("env-1")
    assert (record.phase, record.vmid, record.upid) == (EnvironmentPhase.CLONING, 102, "UPID:clone")


def test_reset_course_refuses_active_environment(store):
    store.create_environment(environment_fixture())
    with pytest.raises(StateConflictError, match="destroy"):
        store.reset_scope("proxmox", "proxmox-admin")


def test_erase_all_can_preserve_only_completed_progress(store):
    seed_completed_in_progress_and_attempts(store)
    store.erase_all(preserve_completed=True)
    assert store.completed_lessons("proxmox", "proxmox-admin") == {"api-access"}
    assert store.list_attempts() == []
```

- [ ] **Step 5: Implement progress/reset semantics and verify GREEN**

`reset_scope` deletes progress and attempt rows only after confirming no matching environment exists. `erase_all(True)` retains only rows with `status='completed'`; `erase_all(False)` removes progress too. Environment deletion is a separate method so lifecycle cleanup must explicitly confirm remote absence first.

Run: `python3.13 -m pytest tests/test_state.py -q && python3.13 -m pytest -q && python3.13 -m mypy src`

- [ ] **Step 6: Commit**

```bash
git add src/learnlab/state.py tests/test_state.py
git commit -m "feat: persist learning and lifecycle state"
```

---

### Task 6: Start Lifecycle and Isolated SSH State

**Files:**
- Create: `src/learnlab/lifecycle.py`
- Create: `src/learnlab/ssh.py`
- Create: `tests/test_lifecycle.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Produces: `LifecycleService.start(StartRequest) -> StartedEnvironment`, `StartRequest`, `StartedEnvironment`, `create_known_hosts(state_root, environment_id) -> Path`, `render_ssh_command(profile, ip, known_hosts) -> str`.
- Consumes: `Provider`, `StateStore`, selected `Course`/`Lesson`, and resolved profile name.

- [ ] **Step 1: Read the TDD test-quality reference before writing tests**

Read `skills/test-driven-development/writing-good-tests.md` through the installed TDD skill package. For each test below, state in a comment during implementation which production change would make it fail; remove those temporary reasoning comments before commit.

- [ ] **Step 2: Write the failing successful-sequence test using a behavioral fake**

Create a `RecordingProvider` implementing the provider protocol with real in-memory behavior and ordered operation recording, not assertion-heavy mocks.

```python
def test_start_persists_remote_boundaries_in_order(store, recording_provider, tmp_path):
    service = LifecycleService(store, recording_provider, tmp_path)
    started = service.start(start_request())
    assert recording_provider.operations == [
        "allocate_vmid", "clone:102", "wait:clone", "locate:102",
        "start:102", "wait:start", "wait_for_ipv4:102",
    ]
    assert started.ip_address == "192.0.2.10"
    assert started.known_hosts.exists()
    record = store.get_environment(started.environment_id)
    assert record.phase is EnvironmentPhase.RUNNING
    assert record.vmid == 102
```

- [ ] **Step 3: Run lifecycle tests and verify RED**

Run: `python3.13 -m pytest tests/test_lifecycle.py::test_start_persists_remote_boundaries_in_order -q`

Expected: import fails because `learnlab.lifecycle` does not exist.

- [ ] **Step 4: Implement the minimum start orchestration**

Follow the 13-step start flow in the spec exactly. Generate environment IDs with `uuid.uuid4()`. VM names use `learnlab-<course-id>-<vmid>` normalized to lowercase ASCII letters, digits, and hyphens and capped at 63 characters. Persist `ALLOCATING`, VMID, `CLONING` plus UPID, discovered node plus `STOPPED`, `STARTING` plus UPID, and `RUNNING` plus IP in separate transactions.

Create the environment directory with mode `0700` and empty `known_hosts` with mode `0600`. Render arguments with `shlex.join(["ssh", "-i", identity, "-o", f"UserKnownHostsFile={known_hosts}", f"{user}@{ip}"])`.

- [ ] **Step 5: Write failing partial-state and duplicate tests**

```python
def test_start_failure_retains_redacted_partial_environment(store, failing_provider, tmp_path):
    failing_provider.fail_on("wait:clone", ProviderTaskFailed("secret-value"))
    with pytest.raises(LifecycleError, match="learnlab destroy"):
        LifecycleService(store, failing_provider, tmp_path, secrets={"secret-value"}).start(start_request())
    [record] = store.list_environments()
    assert record.phase is EnvironmentPhase.FAILED
    assert "secret-value" not in record.error_summary


def test_start_refuses_second_environment_for_course(store, recording_provider, tmp_path):
    service = LifecycleService(store, recording_provider, tmp_path)
    service.start(start_request())
    with pytest.raises(StateConflictError, match="already has an environment"):
        service.start(start_request())
    assert recording_provider.operations.count("allocate_vmid") == 1
```

- [ ] **Step 6: Implement failure retention and verify GREEN**

After the environment row exists, catch provider errors, transition to `FAILED` with a redacted and length-bounded summary, then raise a safe `LifecycleError` directing the user to global destroy. Do not automatically stop or delete.

Run: `python3.13 -m pytest tests/test_lifecycle.py -q && python3.13 -m pytest -q`

- [ ] **Step 7: Commit**

```bash
git add src/learnlab/lifecycle.py src/learnlab/ssh.py tests/test_lifecycle.py tests/conftest.py
git commit -m "feat: orchestrate disposable lesson startup"
```

---

### Task 7: Interactive Course Start and Local Progress

**Files:**
- Modify: `src/learnlab/cli.py`
- Modify: `src/learnlab/state.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Adds: `learnlab start <collection>/<course> [--provider PROFILE]`.
- Adds: `StateStore.start_lesson(...)` and `StateStore.complete_lesson(...)`; v0 CLI marks the selected lesson `in_progress` after successful environment startup and provides `learnlab progress complete <collection>/<course>/<lesson>` to make completion explicit until step validators exist.

- [ ] **Step 1: Write failing default-selection test**

```python
def test_start_defaults_to_first_incomplete_lesson(app_harness):
    app_harness.complete("proxmox", "proxmox-admin", "api-access")
    result = app_harness.invoke(
        ["start", "proxmox/proxmox-admin", "--provider", "home-proxmox"],
        input="\n",
    )
    assert result.exit_code == 0
    assert "2. API Tokens [first incomplete]" in result.stdout
    assert app_harness.lifecycle.requests.one().lesson_id == "api-tokens"
    assert "UserKnownHostsFile=" in result.stdout
```

- [ ] **Step 2: Write failing skip-ahead and all-complete tests**

Assert input `1\n` selects the first lesson even when the second is default. When all lessons are complete, default to lesson one and label all lessons completed. Invalid numeric selections re-prompt without starting infrastructure.

- [ ] **Step 3: Run tests and verify RED**

Run: `python3.13 -m pytest tests/test_cli.py -k 'start_' -q`

Expected: Typer reports `No such command 'start'`.

- [ ] **Step 4: Implement interactive selection and progress presentation**

Load course before provider construction. Show ordered number, title, and one of `[completed]`, `[in progress]`, or `[first incomplete]`. Use `typer.prompt` with the default lesson number. After lifecycle success, mark the selected lesson in progress, show the SSH command, and render step titles and text in order. Do not claim completion automatically.

- [ ] **Step 5: Add and test explicit completion command**

Use exact path `<collection>/<course>/<lesson>`. Reject unknown lessons. After `progress complete`, a later `start` must default to the next incomplete lesson. This narrow command supplies the completion transition until lesson validation is implemented.

- [ ] **Step 6: Verify GREEN and commit**

Run: `python3.13 -m pytest tests/test_cli.py -q && python3.13 -m pytest -q`

```bash
git add src/learnlab/cli.py src/learnlab/state.py tests/test_cli.py
git commit -m "feat: start courses with persistent progress"
```

---

### Task 8: Scoped Reset and Confirmed Global Destroy

**Files:**
- Modify: `src/learnlab/lifecycle.py`
- Modify: `src/learnlab/cli.py`
- Modify: `tests/test_lifecycle.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Adds: `LifecycleService.destroy_all(preserve_completed: bool) -> DestroySummary` and `reset_scope(...)` CLI coordination.
- Adds CLI: `learnlab reset <collection-or-course> [--yes]` and `learnlab destroy [--yes] [--preserve-progress | --erase-progress]`.

- [ ] **Step 1: Write failing destroy lifecycle tests**

```python
def test_destroy_stops_running_vm_then_deletes_and_clears_record(store, recording_provider, tmp_path):
    seed_running_environment(store, environment_id="env-1", vmid=102, node="pve02")
    summary = LifecycleService(store, recording_provider, tmp_path).destroy_all(True)
    assert recording_provider.operations == [
        "locate:102", "stop:102", "wait:stop", "delete:102", "wait:delete", "locate:102",
    ]
    assert summary.destroyed == ["env-1"]
    assert store.list_environments() == []


def test_destroy_absent_vm_clears_local_environment_without_delete(store, recording_provider, tmp_path):
    seed_failed_environment(store, vmid=102)
    recording_provider.vm_exists = False
    LifecycleService(store, recording_provider, tmp_path).destroy_all(True)
    assert "delete:102" not in recording_provider.operations
    assert store.list_environments() == []


def test_destroy_failure_retains_record_and_continues(store, recording_provider, tmp_path):
    seed_two_environments(store)
    recording_provider.fail_for_vmid(102)
    summary = LifecycleService(store, recording_provider, tmp_path).destroy_all(True)
    assert summary.failed == ["env-102"]
    assert summary.destroyed == ["env-103"]
    assert store.get_environment("env-102") is not None
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python3.13 -m pytest tests/test_lifecycle.py -k destroy -q`

Expected: fails because `destroy_all` is absent.

- [ ] **Step 3: Implement idempotent, failure-tolerant destroy**

Locate each VM. If absent, remove its environment directory and record. If running, persist `STOPPING`, stop, and wait for the UPID. Persist `DELETING`, delete, wait, and locate again; only absence permits local deletion. Continue after errors and return a summary. After all environment cleanup, call `erase_all(preserve_completed)` only when no environment records remain; otherwise leave progress untouched and return nonzero at the CLI boundary.

- [ ] **Step 4: Write failing confirmation-policy CLI tests**

```python
def test_destroy_requires_target_confirmation_and_progress_choice(app_harness):
    app_harness.seed_environment(vmid=102)
    result = app_harness.invoke(["destroy"], input="y\ny\n")
    assert "VM 102" in result.stdout
    assert "Preserve completed lessons" in result.stdout
    assert app_harness.lifecycle.destroy_choices == [True]


def test_destroy_yes_still_requires_explicit_progress_policy(app_harness):
    result = app_harness.invoke(["destroy", "--yes"])
    assert result.exit_code == 2
    assert "--preserve-progress or --erase-progress" in result.stdout


def test_destroy_rejects_conflicting_progress_flags(app_harness):
    result = app_harness.invoke(["destroy", "--yes", "--preserve-progress", "--erase-progress"])
    assert result.exit_code == 2
```

Also test that answering `n` to the first prompt makes no provider or state calls.

- [ ] **Step 5: Implement destroy CLI policy**

Display profile, VMID, node, course, and phase for every target before confirmation. Interactive mode asks the infrastructure confirmation and then `Preserve completed lessons? [Y/n]`. `--yes` is valid only with exactly one explicit progress flag. Exit nonzero and list retained environments after partial failure.

- [ ] **Step 6: Write failing reset tests and implement**

Test collection and course scopes separately, refusal with active environments, cancellation without mutation, `--yes`, and malformed three-segment scope. Reset lists affected course/lesson counts before confirmation and delegates deletion to `StateStore.reset_scope`.

- [ ] **Step 7: Verify GREEN and commit**

Run: `python3.13 -m pytest tests/test_lifecycle.py tests/test_cli.py -q && python3.13 -m pytest -q`

```bash
git add src/learnlab/lifecycle.py src/learnlab/cli.py tests/test_lifecycle.py tests/test_cli.py
git commit -m "feat: add confirmed reset and global teardown"
```

---

### Task 9: Documentation and Opt-In Live Acceptance Test

**Files:**
- Create: `README.md`
- Create: `tests/live/test_proxmox_lifecycle.py`
- Create: `tests/live/README.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces documented Debian 13 setup, named-profile configuration, CLI examples, live-test safety contract, and a complete real-provider acceptance test.

- [ ] **Step 1: Write the skipped-by-default live test first**

```python
@pytest.mark.live
def test_real_proxmox_lifecycle_requires_explicit_opt_in():
    if os.environ.get("LEARNLAB_RUN_LIVE_PROXMOX") != "1":
        pytest.skip("set LEARNLAB_RUN_LIVE_PROXMOX=1 to allow real VM mutation")
    settings = load_settings()
    profile_name = os.environ["LEARNLAB_LIVE_PROFILE"]
    provider = build_provider(settings, profile_name)
    vmid = provider.allocate_vmid()
    node = settings.provider(profile_name).node
    try:
        clone_upid = provider.clone(vmid, f"learnlab-live-{vmid}")
        provider.wait_for_task(node, clone_upid, timeout=300)
        location = provider.locate_vm(vmid)
        assert location is not None
        start_upid = provider.start(vmid, location.node)
        provider.wait_for_task(location.node, start_upid, timeout=120)
        assert ipaddress.ip_address(provider.wait_for_ipv4(vmid, location.node, timeout=180)).version == 4
    finally:
        location = provider.locate_vm(vmid)
        if location is not None:
            if location.status == "running":
                provider.wait_for_task(location.node, provider.stop(vmid, location.node), timeout=120)
            provider.wait_for_task(location.node, provider.delete(vmid, location.node), timeout=300)
        assert provider.locate_vm(vmid) is None
```

The test must refuse to run unless both `LEARNLAB_RUN_LIVE_PROXMOX=1` and `LEARNLAB_LIVE_PROFILE` are present. Cleanup remains in `finally` and uses the same production primitives.

- [ ] **Step 2: Verify normal tests do not mutate infrastructure**

Run: `python3.13 -m pytest -m 'not live' -q`

Expected: all offline tests pass and no external connection is attempted.

Run: `python3.13 -m pytest tests/live -q`

Expected: live test is skipped because opt-in is absent.

- [ ] **Step 3: Write README with exact safe setup**

Document Python 3.13 virtual environment creation, editable installation, XDG config location, full named-profile TOML schema, exporting the profile-specific secret environment variable, `provider test`, course start, progress completion, scoped reset, and both interactive and non-interactive destroy forms. State that TLS verification defaults on, live tests mutate infrastructure, and the secret must never be placed in shell history, source, curriculum, TOML, SQLite, or test files.

Describe the proven Checkpoint 05 values only as an example profile and explicitly explain that scoped `SDN.Use` on `/sdn/zones/localnetwork/vmbr0` was needed in that environment.

- [ ] **Step 4: Run full quality gate**

Run:

```bash
python3.13 -m pytest -m 'not live' -q
python3.13 -m ruff check src tests
python3.13 -m ruff format --check src tests
python3.13 -m mypy src
git diff --check
```

Expected: every command passes with no warnings or external network use.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/live pyproject.toml
git commit -m "docs: add safe setup and live acceptance test"
```

---

### Task 10: Final Offline Verification and Manual CLI Smoke Test

**Files:**
- Modify only files implicated by verification failures; every fix starts with a reproducing failing test.

**Interfaces:**
- Verifies all earlier task interfaces together without real infrastructure.

- [ ] **Step 1: Create isolated smoke-test directories outside the repository**

Use `mktemp -d` for temporary `XDG_CONFIG_HOME` and `XDG_STATE_HOME`. Write an example profile whose API URL targets the fake Proxmox server and whose secret environment variable contains only a test value.

- [ ] **Step 2: Run the provider CLI against the fake Proxmox server**

Run `learnlab provider test smoke-proxmox` and verify the output identifies the named profile, every read-only check, and the mutation-permission caveat without printing the test secret.

- [ ] **Step 3: Run start, completion, reset, and destroy CLI tests through Typer's real entry point**

Exercise selection of the default lesson and a skipped-ahead lesson through the existing CLI integration harness. Verify SQLite remains under the temporary state directory, the isolated environment file is mode `0600`, reset refuses active state, and destroy requires both confirmations.

- [ ] **Step 4: Re-run the complete evidence gate**

Run:

```bash
python3.13 -m pytest -m 'not live' -q
python3.13 -m pytest tests/live -q
python3.13 -m ruff check src tests
python3.13 -m ruff format --check src tests
python3.13 -m mypy src
git status --short
git diff --check
```

Expected: offline suite passes, live suite skips, all quality checks pass, and only intentional final documentation changes appear in status.

- [ ] **Step 5: Commit any final test-backed corrections**

If verification required changes, stage only those files and commit with a message describing the corrected behavior. If no files changed, do not create an empty commit.
