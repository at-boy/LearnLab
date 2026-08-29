from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from typer.testing import CliRunner

from learnlab.curriculum import Course, CurriculumError, Lesson, Step
from learnlab.lifecycle import LifecycleError, StartedEnvironment, StartRequest
from learnlab.providers.base import ProviderCheck, ProviderHealth
from learnlab.state import ProgressStatus, StateStore

CONFIG = '''
default_provider = "home-proxmox"

[providers.home-proxmox]
type = "proxmox"
api_url = "https://proxmox.example.test:8006/api2/json"
token_id = "learnlab@pam!automation"
token_secret_env = "LEARNLAB_HOME_SECRET"
template_vmid = 9001
template_name = "debian-12-learning"
node = "pve"
storage = "local-lvm"
network = "vmbr0"
ssh_user = "student"
ssh_identity_file = "~/.ssh/learning-platform"
tls_verify = true
'''


class FakeHealthProvider:
    def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            checks=(ProviderCheck("Template identity", True, "matches"),),
            warnings=("Grant SDN.Use for network vmbr0.",),
        )


class FailedHealthProvider:
    def __init__(self, health: ProviderHealth) -> None:
        self._health = health

    def health_check(self) -> ProviderHealth:
        return self._health


class RecordingCatalog:
    def __init__(self, course: Course) -> None:
        self.course = course
        self.loaded_paths: list[str] = []

    def load_course(self, course_path: str) -> Course:
        self.loaded_paths.append(course_path)
        if course_path != "proxmox/proxmox-admin":
            raise CurriculumError(f"Unknown course: {course_path}")
        return self.course


class RequestLog(list[StartRequest]):
    def one(self) -> StartRequest:
        assert len(self) == 1
        return self[0]


@dataclass
class RecordingLifecycle:
    state_root: Path
    requests: RequestLog = field(default_factory=RequestLog)
    failure: LifecycleError | None = None

    def start(self, request: StartRequest) -> StartedEnvironment:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        known_hosts = self.state_root / "environments" / "env-1" / "known_hosts"
        return StartedEnvironment(
            environment_id="env-1",
            ip_address="192.0.2.10",
            known_hosts=known_hosts,
            ssh_command=(
                "ssh -i /keys/student -o "
                f"UserKnownHostsFile={known_hosts} student@192.0.2.10"
            ),
        )


@dataclass
class AppHarness:
    store: StateStore
    catalog: RecordingCatalog
    lifecycle: RecordingLifecycle
    provider_profiles: list[str]

    def invoke(self, arguments: list[str], input: str | None = None):
        from learnlab.cli import app

        return CliRunner().invoke(app, arguments, input=input)

    def complete(self, collection_id: str, course_id: str, lesson_id: str) -> None:
        self.store.complete_lesson(collection_id, course_id, lesson_id)


@pytest.fixture
def app_harness(
    monkeypatch: pytest.MonkeyPatch, tmp_xdg: Path
) -> AppHarness:
    from learnlab import cli

    course = Course(
        collection_id="proxmox",
        id="proxmox-admin",
        title="Proxmox Administration",
        lessons=(
            Lesson(
                id="api-access",
                title="API Access",
                steps=(
                    Step(
                        id="understand-api",
                        title="Understand the API",
                        content="Review the API boundary.",
                    ),
                    Step(
                        id="locate-endpoint",
                        title="Locate the endpoint",
                        content="Find the documented endpoint.",
                    ),
                ),
            ),
            Lesson(
                id="api-tokens",
                title="API Tokens",
                steps=(
                    Step(
                        id="create-token",
                        title="Create a token",
                        content="Create a dedicated API token.",
                    ),
                    Step(
                        id="limit-token",
                        title="Limit the token",
                        content="Apply least privilege.",
                    ),
                ),
            ),
        ),
    )
    catalog = RecordingCatalog(course)
    store = StateStore(tmp_xdg / "state" / "learnlab" / "state.db")
    store.initialize()
    lifecycle = RecordingLifecycle(tmp_xdg / "state" / "learnlab")
    provider_profiles: list[str] = []

    def provider_factory(settings, profile_name: str):
        assert catalog.loaded_paths
        assert settings.provider(profile_name).name == profile_name
        provider_profiles.append(profile_name)
        return object()

    monkeypatch.setenv("LEARNLAB_HOME_SECRET", "secret")
    monkeypatch.setattr(cli, "catalog_factory", lambda: catalog, raising=False)
    monkeypatch.setattr(cli, "state_store_factory", lambda: store, raising=False)
    monkeypatch.setattr(cli, "state_root", lambda: lifecycle.state_root, raising=False)
    monkeypatch.setattr(cli, "provider_factory", provider_factory)
    monkeypatch.setattr(
        cli,
        "lifecycle_factory",
        lambda *args, **kwargs: lifecycle,
        raising=False,
    )
    return AppHarness(store, catalog, lifecycle, provider_profiles)


@pytest.fixture
def tmp_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path):
    config_dir = tmp_path / "config" / "learnlab"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path


@pytest.fixture
def fake_health_provider() -> FakeHealthProvider:
    return FakeHealthProvider()


def test_provider_test_uses_named_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg,
    fake_health_provider: FakeHealthProvider,
) -> None:
    from learnlab.cli import app

    def provider_factory(
        settings, profile_name: str, client=None
    ) -> FakeHealthProvider:
        assert settings.provider(profile_name).name == "home-proxmox"
        assert client is None
        return fake_health_provider

    monkeypatch.setenv("LEARNLAB_HOME_SECRET", "secret")
    monkeypatch.setattr("learnlab.cli.provider_factory", provider_factory)
    result = CliRunner().invoke(app, ["provider", "test", "home-proxmox"])

    assert result.exit_code == 0
    assert "home-proxmox" in result.stdout
    assert "Template identity" in result.stdout
    assert "SDN.Use" in result.stdout
    assert "secret" not in result.stdout


def test_provider_test_unknown_profile_is_actionable(tmp_xdg) -> None:
    from learnlab.cli import app

    result = CliRunner().invoke(app, ["provider", "test", "missing"])

    assert result.exit_code == 2
    assert "Unknown provider profile: missing" in result.stdout


def test_provider_test_required_check_failure_exits_one(
    monkeypatch: pytest.MonkeyPatch, tmp_xdg
) -> None:
    from learnlab.cli import app

    provider = FailedHealthProvider(
        ProviderHealth(
            checks=(ProviderCheck("Template identity", False, "does not match"),)
        )
    )

    def provider_factory(settings, profile_name: str) -> FailedHealthProvider:
        assert settings.provider(profile_name).name == "home-proxmox"
        return provider

    monkeypatch.setattr("learnlab.cli.provider_factory", provider_factory)
    result = CliRunner().invoke(app, ["provider", "test", "home-proxmox"])

    assert result.exit_code == 1
    assert "FAIL Template identity: does not match" in result.stdout


def test_provider_test_provider_health_failure_exits_three_after_rendering(
    monkeypatch: pytest.MonkeyPatch, tmp_xdg
) -> None:
    from learnlab.cli import app

    provider = FailedHealthProvider(
        ProviderHealth(
            checks=(ProviderCheck("API", False, "request failed"),),
            warnings=("Grant SDN.Use for network vmbr0.",),
            provider_error=True,
        )
    )

    def provider_factory(settings, profile_name: str) -> FailedHealthProvider:
        assert settings.provider(profile_name).name == "home-proxmox"
        return provider

    monkeypatch.setattr("learnlab.cli.provider_factory", provider_factory)
    result = CliRunner().invoke(app, ["provider", "test", "home-proxmox"])

    assert result.exit_code == 3
    assert "FAIL API: request failed" in result.stdout
    assert "SDN.Use" in result.stdout


def test_provider_test_warns_when_tls_verification_is_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_xdg, fake_health_provider: FakeHealthProvider
) -> None:
    from learnlab.cli import app

    config = tmp_xdg / "config" / "learnlab" / "config.toml"
    config.write_text(
        CONFIG.replace("tls_verify = true", "tls_verify = false"), encoding="utf-8"
    )

    def provider_factory(settings, profile_name: str) -> FakeHealthProvider:
        assert settings.provider(profile_name).tls_verify is False
        return fake_health_provider

    monkeypatch.setattr("learnlab.cli.provider_factory", provider_factory)
    result = CliRunner().invoke(app, ["provider", "test", "home-proxmox"])

    assert result.exit_code == 0
    assert "TLS certificate verification is disabled" in result.stdout


def test_start_defaults_to_first_incomplete_lesson(app_harness: AppHarness) -> None:
    app_harness.complete("proxmox", "proxmox-admin", "api-access")

    result = app_harness.invoke(
        ["start", "proxmox/proxmox-admin", "--provider", "home-proxmox"],
        input="\n",
    )

    assert result.exit_code == 0
    assert "1. API Access [completed]" in result.stdout
    assert "2. API Tokens [first incomplete]" in result.stdout
    assert app_harness.lifecycle.requests.one().lesson.id == "api-tokens"
    assert "UserKnownHostsFile=" in result.stdout
    assert app_harness.store.lesson_statuses("proxmox", "proxmox-admin") == {
        "api-access": ProgressStatus.COMPLETED,
        "api-tokens": ProgressStatus.IN_PROGRESS,
    }


def test_start_can_select_a_completed_lesson_before_the_default(
    app_harness: AppHarness,
) -> None:
    app_harness.complete("proxmox", "proxmox-admin", "api-access")

    result = app_harness.invoke(
        ["start", "proxmox/proxmox-admin", "--provider", "home-proxmox"],
        input="1\n",
    )

    assert result.exit_code == 0
    assert app_harness.lifecycle.requests.one().lesson.id == "api-access"


def test_start_defaults_to_first_lesson_when_all_are_complete(
    app_harness: AppHarness,
) -> None:
    app_harness.complete("proxmox", "proxmox-admin", "api-access")
    app_harness.complete("proxmox", "proxmox-admin", "api-tokens")

    result = app_harness.invoke(
        ["start", "proxmox/proxmox-admin", "--provider", "home-proxmox"],
        input="\n",
    )

    assert result.exit_code == 0
    assert "1. API Access [completed]" in result.stdout
    assert "2. API Tokens [completed]" in result.stdout
    assert app_harness.lifecycle.requests.one().lesson.id == "api-access"


def test_start_reprompts_for_invalid_numbers_before_constructing_provider(
    app_harness: AppHarness,
) -> None:
    result = app_harness.invoke(
        ["start", "proxmox/proxmox-admin", "--provider", "home-proxmox"],
        input="0\n3\n",
    )

    assert result.exit_code == 1
    assert result.stdout.count("Select lesson") >= 3
    assert "Choose a lesson number from 1 to 2" in result.stdout
    assert app_harness.provider_profiles == []
    assert app_harness.lifecycle.requests == []


def test_start_renders_selected_lesson_steps_in_order(
    app_harness: AppHarness,
) -> None:
    result = app_harness.invoke(
        ["start", "proxmox/proxmox-admin", "--provider", "home-proxmox"],
        input="2\n",
    )

    assert result.exit_code == 0
    output = result.stdout
    assert output.index("1. Create a token") < output.index(
        "Create a dedicated API token."
    )
    assert output.index("Create a dedicated API token.") < output.index(
        "2. Limit the token"
    )
    assert output.index("2. Limit the token") < output.index(
        "Apply least privilege."
    )
    assert "completed" not in output.split("SSH:", 1)[-1]


def test_start_does_not_mark_progress_when_lifecycle_fails(
    app_harness: AppHarness,
) -> None:
    app_harness.lifecycle.failure = LifecycleError(
        "Environment startup failed with secret"
    )

    result = app_harness.invoke(
        ["start", "proxmox/proxmox-admin", "--provider", "home-proxmox"],
        input="\n",
    )

    assert result.exit_code == 3
    assert "secret" not in result.stdout
    assert "[REDACTED]" in result.stdout
    assert app_harness.store.lesson_statuses("proxmox", "proxmox-admin") == {}


def test_start_labels_an_existing_attempt_in_progress(
    app_harness: AppHarness,
) -> None:
    app_harness.store.start_lesson("proxmox", "proxmox-admin", "api-access")

    result = app_harness.invoke(
        ["start", "proxmox/proxmox-admin"],
        input="1\n",
    )

    assert result.exit_code == 0
    assert "1. API Access [in progress]" in result.stdout


def test_start_uses_default_provider_profile(app_harness: AppHarness) -> None:
    result = app_harness.invoke(
        ["start", "proxmox/proxmox-admin"],
        input="\n",
    )

    assert result.exit_code == 0
    assert app_harness.provider_profiles == ["home-proxmox"]


def test_progress_complete_advances_later_start_default(
    app_harness: AppHarness,
) -> None:
    completed = app_harness.invoke(
        ["progress", "complete", "proxmox/proxmox-admin/api-access"]
    )
    started = app_harness.invoke(
        ["start", "proxmox/proxmox-admin"],
        input="\n",
    )

    assert completed.exit_code == 0
    assert "Completed: proxmox/proxmox-admin/api-access" in completed.stdout
    assert app_harness.lifecycle.requests.one().lesson.id == "api-tokens"
    assert "2. API Tokens [first incomplete]" in started.stdout


def test_progress_complete_rejects_unknown_lesson(app_harness: AppHarness) -> None:
    result = app_harness.invoke(
        ["progress", "complete", "proxmox/proxmox-admin/missing"]
    )

    assert result.exit_code == 2
    assert "Unknown lesson: missing" in result.stdout
    assert app_harness.store.completed_lessons("proxmox", "proxmox-admin") == set()
