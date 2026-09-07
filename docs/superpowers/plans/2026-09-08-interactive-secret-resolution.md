# Interactive Secret Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Securely accept a missing Proxmox token through an interactive hidden prompt or explicit stdin without persisting it.

**Architecture:** Introduce one dependency-injected secret resolver and route every provider-using command through it. Environment input remains first priority; prompt/stdin input is immediately registered with existing redaction and never cached.

**Tech Stack:** Python 3.13 standard library `getpass`, Typer, pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-interactive-secret-resolution-design.md`

## Global Constraints

- Never store secrets in TOML, SQLite, curriculum, files, logs, exceptions, snapshots, URLs, or argv.
- Environment input wins and suppresses all prompts.
- Non-TTY stdin is consumed only with explicit `--token-stdin`.
- Provider-free commands never invoke secret resolution.
- Cancellation occurs before provider access or state mutation.
- Use an isolated worktree and TDD; do not push or merge implicitly.

---

### Task 1: Secret Resolver Domain Service

**Files:**
- Create: `src/learnlab/secrets.py`
- Create: `tests/test_secrets.py`
- Modify: `src/learnlab/config.py`

**Interfaces:**
- Produces: `SecretInputMode(AUTO, STDIN)`.
- Produces: `SecretResolver(environment, prompt, stdin, is_tty)`.
- Produces: `resolve(variable_name: str, profile_name: str, mode=SecretInputMode.AUTO) -> str`.
- Produces: `SecretResolutionError(ConfigurationError)` with secret-free messages.

- [ ] **Step 1: Write priority and interactive tests**

```python
def test_environment_value_wins_without_prompt():
    prompt = ForbiddenPrompt()
    resolver = SecretResolver({"TOKEN": "sentinel"}, prompt, None, lambda: True)
    assert resolver.resolve("TOKEN", "lab") == "sentinel"

def test_missing_interactive_value_uses_hidden_prompt():
    prompt = FakePrompt("entered-secret")
    resolver = SecretResolver({}, prompt, None, lambda: True)
    assert resolver.resolve("TOKEN", "lab") == "entered-secret"
    assert prompt.hidden is True
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_secrets.py -q`

- [ ] **Step 3: Implement strict resolution**

Use an injected prompt callable in tests and `getpass.getpass` in production.
Strip only the trailing newline from stdin; do not trim meaningful secret
whitespace from environment or prompt input. Reject an empty value. Convert
EOF/KeyboardInterrupt into `SecretResolutionError("Secret entry cancelled")`.

- [ ] **Step 4: Add explicit stdin and non-TTY tests**

```python
def test_non_tty_auto_mode_does_not_read_stdin():
    resolver = SecretResolver({}, ForbiddenPrompt(), ForbiddenReader(), lambda: False)
    with pytest.raises(SecretResolutionError, match="TOKEN"):
        resolver.resolve("TOKEN", "lab")

def test_stdin_mode_reads_exactly_one_line():
    resolver = SecretResolver({}, ForbiddenPrompt(), io.StringIO("secret\nextra\n"), lambda: False)
    assert resolver.resolve("TOKEN", "lab", SecretInputMode.STDIN) == "secret"
```

- [ ] **Step 5: Verify and commit**

```bash
git add src/learnlab/secrets.py src/learnlab/config.py tests/test_secrets.py
git commit -m "feat: resolve provider secrets interactively"
```

---

### Task 2: Integrate Provider Test and Validation

**Files:**
- Modify: `src/learnlab/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Adds `--token-stdin` to `provider test` and provider-aware `validate`.
- Replaces direct `resolve_token_secret(profile)` calls with `secret_resolver_factory()`.

- [ ] **Step 1: Write CLI prompt, stdin, and redaction tests**

```python
def test_provider_test_prompts_when_environment_missing(runner, fake_resolver):
    result = runner.invoke(app, ["provider", "test", "lab"])
    assert result.exit_code == 0
    assert fake_resolver.requests == [("TOKEN", "lab", "auto")]

def test_provider_error_never_prints_prompted_secret(runner):
    result = runner.invoke(app, ["provider", "test", "lab"])
    assert "entered-secret" not in result.stdout
```

- [ ] **Step 2: Verify RED and integrate one resolver path**

Run: `.venv/bin/python -m pytest tests/test_cli.py -k 'provider_test or token_stdin' -q`

Add each resolved value to the command redaction set before constructing the
provider. Make `--token-stdin` a boolean Typer option and pass the explicit mode.

- [ ] **Step 3: Verify and commit**

```bash
git add src/learnlab/cli.py tests/test_cli.py
git commit -m "feat: accept secure secrets for provider checks"
```

---

### Task 3: Integrate Start, Resume, Continue, and Destroy

**Files:**
- Modify: `src/learnlab/cli.py`
- Modify: `src/learnlab/lifecycle.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_lifecycle.py`

- [ ] **Step 1: Write lazy-resolution tests for every command family**

```python
def test_none_course_never_prompts_for_secret(runner, forbidden_resolver):
    result = runner.invoke(app, ["start", "concepts/intro"])
    assert result.exit_code == 0

def test_cancelled_secret_stops_before_lifecycle(runner, lifecycle_spy):
    result = runner.invoke(app, ["start", "demo/admin"])
    assert result.exit_code == 2
    assert lifecycle_spy.calls == []
```

- [ ] **Step 2: Verify RED and thread input mode through lazy dependencies**

Run: `.venv/bin/python -m pytest tests/test_cli.py tests/test_lifecycle.py -k secret -q`

Extend `_LazySessionDependencyResolver` with `secret_resolver` and `secret_mode`.
Resolve only after effective policy proves a provider is required. Destruction
may involve multiple profiles; prompt once per distinct variable and cache only
within that command process.

- [ ] **Step 3: Verify interruption and redaction regressions**

Run: `.venv/bin/python -m pytest tests/test_cli.py tests/test_lifecycle.py tests/test_session.py -q`

- [ ] **Step 4: Commit**

```bash
git add src/learnlab/cli.py src/learnlab/lifecycle.py tests/test_cli.py tests/test_lifecycle.py
git commit -m "feat: prompt lazily for course provider secrets"
```

---

### Task 4: Documentation and Complete Gate

**Files:**
- Modify: `README.md`
- Modify: `docs/LearnLab-Course-Authoring-Guide.md`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Document three supported flows**

Show environment-variable automation, hidden interactive entry, and a generic
password-manager command piped to `--token-stdin`. State that no secret is
remembered and plain non-TTY stdin is ignored.

- [ ] **Step 2: Run secret leakage and full regression tests**

Run: `.venv/bin/python -m pytest -m 'not live' -q`

Run: `.venv/bin/ruff check .`

Run: `.venv/bin/mypy src`

Run: `git diff --check`

- [ ] **Step 3: Commit**

```bash
git add README.md docs/LearnLab-Course-Authoring-Guide.md tests/test_config.py
git commit -m "docs: explain secure token input"
```
