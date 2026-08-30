from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from typer.testing import CliRunner

from learnlab.curriculum import Course, CurriculumError, Lesson, Step
from learnlab.lifecycle import (
    DestroySummary,
    LifecycleError,
    StartedEnvironment,
    StartRequest,
)
from learnlab.providers.base import ProviderCheck, ProviderHealth
from learnlab.state import (
    EnvironmentPhase,
    EnvironmentRecord,
    ProgressStatus,
    StateStore,
)

CONFIG = """
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

[providers.lab-proxmox]
type = "proxmox"
api_url = "https://lab-proxmox.example.test:8006/api2/json"
token_id = "learnlab@pam!automation"
token_secret_env = "LEARNLAB_HOME_SECRET"
template_vmid = 9001
template_name = "debian-12-learning"
node = "lab-pve"
storage = "local-lvm"
network = "vmbr0"
ssh_user = "student"
ssh_identity_file = "~/.ssh/learning-platform"
tls_verify = true

[providers.missing-secret]
type = "proxmox"
api_url = "https://missing-secret.example.test:8006/api2/json"
token_id = "learnlab@pam!automation"
token_secret_env = "LEARNLAB_MISSING_SECRET"
template_vmid = 9001
template_name = "debian-12-learning"
node = "missing-pve"
storage = "local-lvm"
network = "vmbr0"
ssh_user = "student"
ssh_identity_file = "~/.ssh/learning-platform"
tls_verify = true
"""


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


class CliDestroyProvider:
    """Behavioral destroy provider used by CLI/lifecycle integration tests."""

    def __init__(self, vmid: int, node: str) -> None:
        self.vmid = vmid
        self.node = node
        self.present = True
        self.operations: list[str] = []

    def locate_vm(self, vmid: int):
        from learnlab.providers.base import VmLocation

        self.operations.append(f"locate:{vmid}")
        if not self.present:
            return None
        return VmLocation(node=self.node, status="stopped")

    def delete(self, vmid: int, node: str) -> str:
        self.operations.append(f"delete:{vmid}")
        self.present = False
        return "delete"

    def wait_for_task(self, node: str, upid: str, timeout: float) -> None:
        self.operations.append(f"wait:{upid}")


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
    store: StateStore
    requests: RequestLog = field(default_factory=RequestLog)
    failure: LifecycleError | None = None
    destroy_choices: list[bool] = field(default_factory=list)
    destroy_targets: list[tuple[str, ...]] = field(default_factory=list)
    destroy_summary: DestroySummary | None = None

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

    def destroy_all(
        self,
        preserve_completed: bool,
        confirmed_environments: tuple[EnvironmentRecord, ...],
    ) -> DestroySummary:
        self.destroy_choices.append(preserve_completed)
        self.destroy_targets.append(
            tuple(environment.id for environment in confirmed_environments)
        )
        if self.destroy_summary is not None:
            return self.destroy_summary
        destroyed = [environment.id for environment in confirmed_environments]
        for environment_id in destroyed:
            self.store.delete_environment(environment_id)
        if not self.store.list_environments():
            self.store.erase_all(preserve_completed)
        return DestroySummary(destroyed=destroyed, failed=[])


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

    def seed_environment(
        self,
        *,
        environment_id: str = "env-1",
        course_id: str = "proxmox-admin",
        vmid: int = 102,
        node: str = "pve02",
        profile_name: str = "home-proxmox",
        phase: EnvironmentPhase = EnvironmentPhase.RUNNING,
    ) -> None:
        self.store.create_environment(
            EnvironmentRecord(
                id=environment_id,
                collection_id="proxmox",
                course_id=course_id,
                lesson_id="api-access",
                attempt_id=None,
                profile_name=profile_name,
                provider_type="proxmox",
                phase=phase,
                vmid=vmid,
                node=node,
            )
        )


@pytest.fixture
def app_harness(monkeypatch: pytest.MonkeyPatch, tmp_xdg: Path) -> AppHarness:
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
    lifecycle = RecordingLifecycle(tmp_xdg / "state" / "learnlab", store)
    provider_profiles: list[str] = []

    def provider_factory(settings, profile_name: str):
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
    assert output.index("2. Limit the token") < output.index("Apply least privilege.")
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


def test_destroy_requires_target_confirmation_and_progress_choice(
    app_harness: AppHarness,
) -> None:
    app_harness.seed_environment(vmid=102)

    result = app_harness.invoke(["destroy"], input="y\ny\n")

    assert result.exit_code == 0
    assert "Profile: home-proxmox" in result.stdout
    assert "VM 102" in result.stdout
    assert "Node: pve02" in result.stdout
    assert "Course: proxmox/proxmox-admin" in result.stdout
    assert "Phase: running" in result.stdout
    assert "Preserve completed lessons" in result.stdout
    assert app_harness.lifecycle.destroy_choices == [True]


def test_destroy_cancellation_makes_no_provider_or_lifecycle_call(
    app_harness: AppHarness,
) -> None:
    app_harness.seed_environment(vmid=102)

    result = app_harness.invoke(["destroy"], input="n\n")

    assert result.exit_code == 0
    assert "VM 102" in result.stdout
    assert app_harness.provider_profiles == []
    assert app_harness.lifecycle.destroy_choices == []
    assert [record.id for record in app_harness.store.list_environments()] == ["env-1"]


def test_destroy_yes_still_requires_explicit_progress_policy(
    app_harness: AppHarness,
) -> None:
    result = app_harness.invoke(["destroy", "--yes"])

    assert result.exit_code == 2
    assert "--preserve-progress or --erase-progress" in result.stdout
    assert app_harness.provider_profiles == []
    assert app_harness.lifecycle.destroy_choices == []


def test_destroy_rejects_conflicting_progress_flags(
    app_harness: AppHarness,
) -> None:
    result = app_harness.invoke(
        ["destroy", "--yes", "--preserve-progress", "--erase-progress"]
    )

    assert result.exit_code == 2
    assert "exactly one" in result.stdout
    assert app_harness.provider_profiles == []
    assert app_harness.lifecycle.destroy_choices == []


@pytest.mark.parametrize(
    ("flag", "expected_choice"),
    [("--preserve-progress", True), ("--erase-progress", False)],
)
def test_destroy_yes_uses_explicit_progress_policy(
    app_harness: AppHarness, flag: str, expected_choice: bool
) -> None:
    app_harness.seed_environment(vmid=102)

    result = app_harness.invoke(["destroy", "--yes", flag])

    assert result.exit_code == 0
    assert app_harness.lifecycle.destroy_choices == [expected_choice]


def test_destroy_partial_failure_exits_nonzero_and_lists_retained_environment(
    app_harness: AppHarness,
) -> None:
    app_harness.seed_environment(environment_id="env-102", vmid=102)
    app_harness.lifecycle.destroy_summary = DestroySummary(
        destroyed=[], failed=["env-102"]
    )

    result = app_harness.invoke(["destroy", "--yes", "--preserve-progress"])

    assert result.exit_code == 3
    assert "Retained environment: env-102" in result.stdout
    assert "VM 102" in result.stdout


def test_destroy_constructs_every_recorded_provider_profile(
    app_harness: AppHarness,
) -> None:
    app_harness.seed_environment(
        environment_id="env-home",
        course_id="proxmox-admin",
        profile_name="home-proxmox",
        vmid=102,
    )
    app_harness.seed_environment(
        environment_id="env-lab",
        course_id="linux-basics",
        profile_name="lab-proxmox",
        vmid=102,
    )
    app_harness.seed_environment(
        environment_id="env-home-two",
        course_id="networking-basics",
        profile_name="home-proxmox",
        vmid=104,
    )

    result = app_harness.invoke(["destroy", "--yes", "--preserve-progress"])

    assert result.exit_code == 0
    assert app_harness.provider_profiles == ["home-proxmox", "lab-proxmox"]


def test_destroy_passes_only_the_pre_confirmation_snapshot(
    app_harness: AppHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from learnlab import cli

    app_harness.seed_environment(
        environment_id="env-confirmed",
        course_id="proxmox-admin",
        vmid=102,
    )

    def inserting_provider_factory(settings, profile_name: str):
        app_harness.seed_environment(
            environment_id="env-later",
            course_id="linux-basics",
            vmid=103,
        )
        return object()

    monkeypatch.setattr(cli, "provider_factory", inserting_provider_factory)

    result = app_harness.invoke(["destroy", "--yes", "--preserve-progress"])

    assert result.exit_code == 0
    assert app_harness.lifecycle.destroy_targets == [("env-confirmed",)]
    assert app_harness.store.get_environment("env-confirmed") is None
    assert app_harness.store.get_environment("env-later") is not None


def test_destroy_missing_secret_profile_does_not_block_valid_target(
    app_harness: AppHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from learnlab import cli
    from learnlab.lifecycle import LifecycleService

    app_harness.seed_environment(
        environment_id="env-invalid",
        profile_name="missing-secret",
        course_id="proxmox-admin",
        vmid=102,
    )
    app_harness.seed_environment(
        environment_id="env-valid",
        profile_name="home-proxmox",
        course_id="linux-basics",
        vmid=103,
        node="pve03",
    )
    valid_provider = CliDestroyProvider(103, "pve03")
    constructed_profiles: list[str] = []

    def provider_factory(settings, profile_name: str):
        constructed_profiles.append(profile_name)
        assert profile_name == "home-proxmox"
        return valid_provider

    monkeypatch.setattr(cli, "provider_factory", provider_factory)
    monkeypatch.setattr(cli, "lifecycle_factory", LifecycleService)

    result = app_harness.invoke(["destroy", "--yes", "--preserve-progress"])

    retained = app_harness.store.get_environment("env-invalid")
    assert result.exit_code == 3
    assert constructed_profiles == ["home-proxmox"]
    assert valid_provider.operations == [
        "locate:103",
        "delete:103",
        "wait:delete",
        "locate:103",
    ]
    assert retained is not None
    assert retained.phase is EnvironmentPhase.FAILED
    assert "LEARNLAB_MISSING_SECRET" in (retained.error_summary or "")
    assert app_harness.store.get_environment("env-valid") is None
    assert "Retained environment: env-invalid" in result.stdout


def test_destroy_malformed_profile_table_does_not_block_valid_target(
    app_harness: AppHarness,
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli
    from learnlab.lifecycle import LifecycleService

    config = tmp_xdg / "config" / "learnlab" / "config.toml"
    config.write_text(
        CONFIG.replace('node = "lab-pve"\n', ""),
        encoding="utf-8",
    )
    app_harness.seed_environment(
        environment_id="env-malformed",
        profile_name="lab-proxmox",
        course_id="proxmox-admin",
        vmid=102,
    )
    app_harness.seed_environment(
        environment_id="env-valid",
        profile_name="home-proxmox",
        course_id="linux-basics",
        vmid=103,
        node="pve03",
    )
    valid_provider = CliDestroyProvider(103, "pve03")
    constructed_profiles: list[str] = []

    def provider_factory(settings, profile_name: str):
        constructed_profiles.append(profile_name)
        assert profile_name == "home-proxmox"
        return valid_provider

    monkeypatch.setattr(cli, "provider_factory", provider_factory)
    monkeypatch.setattr(cli, "lifecycle_factory", LifecycleService)

    result = app_harness.invoke(["destroy", "--yes", "--preserve-progress"])

    retained = app_harness.store.get_environment("env-malformed")
    assert result.exit_code == 3
    assert constructed_profiles == ["home-proxmox"]
    assert valid_provider.operations == [
        "locate:103",
        "delete:103",
        "wait:delete",
        "locate:103",
    ]
    assert retained is not None
    assert retained.phase is EnvironmentPhase.FAILED
    assert "Invalid provider profile lab-proxmox" in (retained.error_summary or "")
    assert "missing keys: node" in (retained.error_summary or "")
    assert app_harness.store.get_environment("env-valid") is None
    assert "Retained environment: env-malformed" in result.stdout


@pytest.mark.parametrize(
    ("arguments", "user_input", "expects_progress_prompt"),
    [
        (["destroy"], "n\n", False),
        (["destroy"], "y\n\n", True),
        (["destroy", "--yes", "--preserve-progress"], None, False),
    ],
)
def test_destroy_fresh_state_does_not_create_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
    arguments: list[str],
    user_input: str | None,
    expects_progress_prompt: bool,
) -> None:
    from learnlab import cli

    fresh_state_root = tmp_xdg / "fresh-state" / "learnlab"
    monkeypatch.setattr(cli, "state_root", lambda: fresh_state_root)
    monkeypatch.setattr(
        cli,
        "state_store_factory",
        lambda: StateStore(fresh_state_root / "state.db"),
    )
    monkeypatch.setattr(
        cli,
        "provider_factory",
        lambda *args, **kwargs: pytest.fail("provider must not be constructed"),
    )
    monkeypatch.setattr(
        cli,
        "lifecycle_factory",
        lambda *args, **kwargs: pytest.fail("lifecycle must not be constructed"),
    )

    result = CliRunner().invoke(cli.app, arguments, input=user_input)

    assert result.exit_code == 0
    assert ("Preserve completed lessons" in result.stdout) is expects_progress_prompt
    assert not fresh_state_root.exists()


@pytest.mark.parametrize("policy_flag", ["--preserve-progress", "--erase-progress"])
def test_destroy_interactive_policy_flags_are_rejected_without_yes(
    app_harness: AppHarness,
    policy_flag: str,
) -> None:
    app_harness.seed_environment(vmid=102)

    result = app_harness.invoke(["destroy", policy_flag], input="y\ny\n")

    assert result.exit_code == 2
    assert f"{policy_flag} requires --yes" in result.stdout
    assert app_harness.lifecycle.destroy_choices == []
    assert app_harness.provider_profiles == []
    assert app_harness.store.get_environment("env-1") is not None


def test_reset_course_lists_scope_and_counts_before_confirmation(
    app_harness: AppHarness,
) -> None:
    seed_progress(
        app_harness.store,
        "proxmox",
        "proxmox-admin",
        ("api-access", "api-tokens"),
    )

    result = app_harness.invoke(["reset", "proxmox/proxmox-admin"], input="y\n")

    assert result.exit_code == 0
    assert "Scope: proxmox/proxmox-admin" in result.stdout
    assert "Affected courses: 1" in result.stdout
    assert "Affected lessons: 2" in result.stdout
    assert result.stdout.index("Affected lessons: 2") < result.stdout.index("Continue?")
    assert app_harness.store.lesson_statuses("proxmox", "proxmox-admin") == {}
    assert app_harness.store.list_attempts() == []


def test_reset_collection_removes_only_matching_collection(
    app_harness: AppHarness,
) -> None:
    seed_progress(
        app_harness.store,
        "proxmox",
        "proxmox-admin",
        ("api-access", "api-tokens"),
    )
    seed_progress(app_harness.store, "proxmox", "linux-basics", ("shell",))
    seed_progress(app_harness.store, "cloud", "cloud-basics", ("identity",))

    result = app_harness.invoke(["reset", "proxmox"], input="y\n")

    assert result.exit_code == 0
    assert "Scope: proxmox" in result.stdout
    assert "Affected courses: 2" in result.stdout
    assert "Affected lessons: 3" in result.stdout
    assert app_harness.store.lesson_statuses("proxmox", "proxmox-admin") == {}
    assert app_harness.store.lesson_statuses("proxmox", "linux-basics") == {}
    assert app_harness.store.completed_lessons("cloud", "cloud-basics") == {"identity"}
    assert {
        (attempt.collection_id, attempt.course_id)
        for attempt in app_harness.store.list_attempts()
    } == {("cloud", "cloud-basics")}


def test_reset_refuses_matching_environment_without_mutating_progress(
    app_harness: AppHarness,
) -> None:
    seed_progress(app_harness.store, "proxmox", "proxmox-admin", ("api-access",))
    app_harness.seed_environment(vmid=102)

    result = app_harness.invoke(["reset", "proxmox/proxmox-admin", "--yes"])

    assert result.exit_code == 3
    assert "learnlab destroy" in result.stdout
    assert app_harness.store.completed_lessons("proxmox", "proxmox-admin") == {
        "api-access"
    }
    assert app_harness.store.get_environment("env-1") is not None


def test_reset_cancellation_makes_no_state_mutation(
    app_harness: AppHarness,
) -> None:
    seed_progress(app_harness.store, "proxmox", "proxmox-admin", ("api-access",))

    result = app_harness.invoke(["reset", "proxmox/proxmox-admin"], input="n\n")

    assert result.exit_code == 0
    assert "Cancelled." in result.stdout
    assert app_harness.store.completed_lessons("proxmox", "proxmox-admin") == {
        "api-access"
    }
    assert len(app_harness.store.list_attempts()) == 1


def test_reset_yes_skips_confirmation(app_harness: AppHarness) -> None:
    seed_progress(app_harness.store, "proxmox", "proxmox-admin", ("api-access",))

    result = app_harness.invoke(["reset", "proxmox/proxmox-admin", "--yes"])

    assert result.exit_code == 0
    assert "Continue?" not in result.stdout
    assert app_harness.store.lesson_statuses("proxmox", "proxmox-admin") == {}


def test_reset_rejects_three_segment_scope_without_mutation(
    app_harness: AppHarness,
) -> None:
    seed_progress(app_harness.store, "proxmox", "proxmox-admin", ("api-access",))

    result = app_harness.invoke(["reset", "proxmox/proxmox-admin/api-access", "--yes"])

    assert result.exit_code == 2
    assert "collection or collection/course" in result.stdout
    assert app_harness.store.completed_lessons("proxmox", "proxmox-admin") == {
        "api-access"
    }


def seed_progress(
    store: StateStore,
    collection_id: str,
    course_id: str,
    lesson_ids: tuple[str, ...],
) -> None:
    for lesson_id in lesson_ids:
        store.complete_lesson(collection_id, course_id, lesson_id)
        store.create_attempt(collection_id, course_id, lesson_id)
