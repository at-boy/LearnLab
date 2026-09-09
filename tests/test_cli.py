from __future__ import annotations

import json
import shutil
import sqlite3
import threading
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from types import MappingProxyType

import pytest
from typer.testing import CliRunner

from learnlab.curriculum import (
    Course,
    CurriculumError,
    EnvironmentPolicy,
    EnvironmentScope,
    Lesson,
    Step,
    Verification,
    VerificationType,
)
from learnlab.lifecycle import (
    PROVISIONING_INTERRUPTED_GUIDANCE,
    DestroySummary,
    EnvironmentResolution,
    LifecycleError,
    ProvisioningInterrupted,
    StartedEnvironment,
    StartRequest,
)
from learnlab.progress import ProgressEvent, ProgressKind
from learnlab.providers.base import ProviderCheck, ProviderHealth
from learnlab.session import SessionAction, SessionOutcome
from learnlab.state import (
    CompletionSource,
    EnvironmentPhase,
    EnvironmentRecord,
    ProgressStatus,
    StateConflictError,
    StateStore,
)

CONFIG = """
default_provider = "home-proxmox"

[providers.home-proxmox]
type = "proxmox"
api_url = "https://proxmox.example.test:8006"
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
api_url = "https://lab-proxmox.example.test:8006"
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
api_url = "https://missing-secret.example.test:8006"
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

SNAPSHOTS = Path(__file__).parent / "snapshots"


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
        self.api_origin = "https://proxmox.example.test:8006"
        self.profile_fingerprint = "test-provider-fingerprint"

    def locate_vm(self, vmid: int):
        from learnlab.providers.base import VmLocation

        self.operations.append(f"locate:{vmid}")
        if not self.present:
            return None
        return VmLocation(
            node=self.node,
            status="stopped",
            name=f"learnlab-linux-basics-{vmid}",
        )

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

    def ensure_environment(
        self,
        request: StartRequest,
        policy: EnvironmentPolicy,
        replace_confirmed: bool = False,
    ) -> EnvironmentResolution:
        existing = self.store.active_environment(
            request.course.collection_id, request.course.id
        )
        if existing is not None:
            self.requests.append(request)
            return EnvironmentResolution("reused", existing)
        started = self.start(request)
        return EnvironmentResolution("created", started=started)

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
class SessionLifecycle:
    resolution: EnvironmentResolution = EnvironmentResolution("none")
    calls: list[tuple[str, EnvironmentScope, bool]] = field(default_factory=list)

    def ensure_environment(
        self,
        request: StartRequest,
        policy: EnvironmentPolicy,
        replace_confirmed: bool = False,
    ) -> EnvironmentResolution:
        self.calls.append((request.lesson.id, policy.scope, replace_confirmed))
        return self.resolution


class ReplacementSessionLifecycle(SessionLifecycle):
    def __init__(self, existing: EnvironmentRecord) -> None:
        super().__init__()
        self.existing = existing

    def ensure_environment(
        self,
        request: StartRequest,
        policy: EnvironmentPolicy,
        replace_confirmed: bool = False,
    ) -> EnvironmentResolution:
        self.calls.append((request.lesson.id, policy.scope, replace_confirmed))
        if not replace_confirmed:
            return EnvironmentResolution("replacement_required", self.existing)
        return EnvironmentResolution("created")


class InterruptedReplacementSessionLifecycle(ReplacementSessionLifecycle):
    def ensure_environment(
        self,
        request: StartRequest,
        policy: EnvironmentPolicy,
        replace_confirmed: bool = False,
    ) -> EnvironmentResolution:
        self.calls.append((request.lesson.id, policy.scope, replace_confirmed))
        if not replace_confirmed:
            return EnvironmentResolution("replacement_required", self.existing)
        raise ProvisioningInterrupted(PROVISIONING_INTERRUPTED_GUIDANCE)


class BlockingSessionLifecycle(SessionLifecycle):
    def __init__(
        self,
        progress,
        entered: threading.Event,
        release: threading.Event,
    ) -> None:
        super().__init__(EnvironmentResolution("created"))
        self.progress = progress
        self.entered = entered
        self.release = release

    def ensure_environment(
        self,
        request: StartRequest,
        policy: EnvironmentPolicy,
        replace_confirmed: bool = False,
    ) -> EnvironmentResolution:
        self.progress.on_progress(
            ProgressEvent(
                ProgressKind.ENVIRONMENT_REQUESTED,
                "Creating lesson environment",
                0,
            )
        )
        self.entered.set()
        if not self.release.wait(timeout=5):
            raise AssertionError("test did not release lifecycle")
        return super().ensure_environment(request, policy, replace_confirmed)


class ProvisioningInterruptedLifecycle(SessionLifecycle):
    def ensure_environment(
        self,
        request: StartRequest,
        policy: EnvironmentPolicy,
        replace_confirmed: bool = False,
    ) -> EnvironmentResolution:
        raise ProvisioningInterrupted(PROVISIONING_INTERRUPTED_GUIDANCE)


class ContinuingBlockingSessionLifecycle(SessionLifecycle):
    def __init__(
        self,
        progress,
        second_entered: threading.Event,
        release_second: threading.Event,
    ) -> None:
        super().__init__(EnvironmentResolution("created"))
        self.progress = progress
        self.second_entered = second_entered
        self.release_second = release_second

    def ensure_environment(
        self,
        request: StartRequest,
        policy: EnvironmentPolicy,
        replace_confirmed: bool = False,
    ) -> EnvironmentResolution:
        self.calls.append((request.lesson.id, policy.scope, replace_confirmed))
        self.progress.on_progress(
            ProgressEvent(
                ProgressKind.ENVIRONMENT_REQUESTED,
                "Creating lesson environment",
                0,
            )
        )
        if len(self.calls) == 1:
            self.progress.on_progress(
                ProgressEvent(
                    ProgressKind.ENVIRONMENT_READY,
                    "Environment is ready",
                    1,
                )
            )
            return self.resolution
        self.second_entered.set()
        if not self.release_second.wait(timeout=5):
            raise AssertionError("test did not release second lesson lifecycle")
        return self.resolution


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
                provider_endpoint=(
                    "https://lab-proxmox.example.test:8006"
                    if profile_name == "lab-proxmox"
                    else "https://proxmox.example.test:8006"
                ),
                provider_fingerprint="test-provider-fingerprint",
                expected_vm_name=f"learnlab-{course_id}-{vmid}",
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
                        verifications=(
                            Verification(
                                id="confirm",
                                type=VerificationType.MANUAL_CONFIRMATION,
                                prompt="Confirm the API boundary.",
                            ),
                        ),
                    ),
                    Step(
                        id="locate-endpoint",
                        title="Locate the endpoint",
                        content="Find the documented endpoint.",
                        verifications=(
                            Verification(
                                id="confirm",
                                type=VerificationType.MANUAL_CONFIRMATION,
                                prompt="Confirm the endpoint.",
                            ),
                        ),
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
                        verifications=(
                            Verification(
                                id="confirm",
                                type=VerificationType.MANUAL_CONFIRMATION,
                                prompt="Confirm the token.",
                            ),
                        ),
                    ),
                    Step(
                        id="limit-token",
                        title="Limit the token",
                        content="Apply least privilege.",
                        verifications=(
                            Verification(
                                id="confirm",
                                type=VerificationType.MANUAL_CONFIRMATION,
                                prompt="Confirm least privilege.",
                            ),
                        ),
                    ),
                ),
            ),
        ),
        environment=EnvironmentPolicy(EnvironmentScope.COURSE, "proxmox.vm"),
    )
    catalog = RecordingCatalog(course)
    store = StateStore(tmp_xdg / "state" / "learnlab" / "state.db")
    store.initialize()
    lifecycle = RecordingLifecycle(tmp_xdg / "state" / "learnlab", store)
    provider_profiles: list[str] = []

    def provider_factory(settings, profile_name: str, secret=None):
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


def session_lesson(
    lesson_id: str = "basics",
    title: str = "Basics",
    *,
    checks: tuple[Verification, ...] | None = None,
    environment: EnvironmentPolicy | None = None,
) -> Lesson:
    declared_checks = checks or (
        Verification(
            id="confirm",
            type=VerificationType.MANUAL_CONFIRMATION,
            prompt="Confirm the result.",
        ),
    )
    return Lesson(
        id=lesson_id,
        title=title,
        steps=(
            Step(
                id="inspect",
                title="Inspect the system",
                instructions="Inspect the system before continuing.",
                verifications=declared_checks,
            ),
        ),
        environment=environment,
    )


def session_course(
    scope: EnvironmentScope,
    *,
    lessons: tuple[Lesson, ...] | None = None,
) -> Course:
    return Course(
        collection_id="proxmox",
        id="proxmox-admin",
        title="Proxmox Administration",
        lessons=lessons or (session_lesson(),),
        environment=EnvironmentPolicy(
            scope,
            "proxmox.vm" if scope is not EnvironmentScope.NONE else None,
        ),
    )


def install_session_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
    course: Course,
    lifecycle,
) -> tuple[StateStore, list[tuple[str, str | None]]]:
    from learnlab import cli

    store = StateStore(tmp_xdg / "session-state" / "learnlab.db")
    store.initialize()
    providers: list[tuple[str, str | None]] = []

    monkeypatch.setenv("LEARNLAB_HOME_SECRET", "secret")
    monkeypatch.setattr(cli, "catalog_factory", lambda: RecordingCatalog(course))
    monkeypatch.setattr(cli, "state_store_factory", lambda: store)
    monkeypatch.setattr(cli, "state_root", lambda: tmp_xdg / "session-state")
    monkeypatch.setattr(
        cli,
        "provider_factory",
        lambda settings, profile_name, secret=None: (
            providers.append((profile_name, secret)) or object()
        ),
    )
    monkeypatch.setattr(cli, "lifecycle_factory", lifecycle)
    return store, providers


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


def test_resume_without_course_state_exits_two_and_directs_to_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    lifecycle = SessionLifecycle()
    install_session_cli(
        monkeypatch,
        tmp_xdg,
        session_course(EnvironmentScope.NONE),
        lambda *args, **kwargs: lifecycle,
    )

    result = CliRunner().invoke(
        __import__("learnlab.cli", fromlist=["app"]).app,
        ["resume", "proxmox/proxmox-admin"],
    )

    assert result.exit_code == 2
    assert "use learnlab start" in result.stdout
    assert lifecycle.calls == []


def test_none_scoped_start_skips_provider_config_and_runs_interactive_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli

    lifecycle = SessionLifecycle()
    store, providers = install_session_cli(
        monkeypatch,
        tmp_xdg,
        session_course(EnvironmentScope.NONE),
        lambda *args, **kwargs: lifecycle,
    )
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: pytest.fail("none scope must not load provider configuration"),
    )
    monkeypatch.setattr(
        cli,
        "resolve_token_secret",
        lambda profile: pytest.fail("none scope must not resolve a secret"),
    )

    result = CliRunner().invoke(
        cli.app,
        ["start", "proxmox/proxmox-admin", "--provider", "missing"],
        input="\n\ny\nq\n",
    )

    assert result.exit_code == 0
    assert "Selected lesson: Basics" in result.stdout
    assert "Environment policy: none" in result.stdout
    assert "Step 1 of 1: Inspect the system" in result.stdout
    assert "Verification 1 of 1: confirm" in result.stdout
    assert "PASS (self-attested): Learner confirmed" in result.stdout
    assert "Progress saved." in result.stdout
    assert providers == []
    assert lifecycle.calls == [("basics", EnvironmentScope.NONE, False)]
    assert store.completed_lessons("proxmox", "proxmox-admin") == {"basics"}


def test_none_to_provider_transition_resolves_configuration_only_when_entered(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli

    course = session_course(
        EnvironmentScope.COURSE,
        lessons=(
            session_lesson(
                "first",
                "Provider-Free First",
                environment=EnvironmentPolicy(EnvironmentScope.NONE),
            ),
            session_lesson("second", "Provider Second"),
        ),
    )
    lifecycle = SessionLifecycle()
    store, providers = install_session_cli(
        monkeypatch,
        tmp_xdg,
        course,
        lambda *args, **kwargs: lifecycle,
    )
    real_load_settings = cli.load_settings
    settings_snapshots: list[set[str]] = []

    def load_after_none_lesson():
        completed = store.completed_lessons("proxmox", "proxmox-admin")
        settings_snapshots.append(completed)
        assert completed == {"first"}
        return real_load_settings()

    monkeypatch.setattr(cli, "load_settings", load_after_none_lesson)

    result = CliRunner().invoke(
        cli.app,
        ["start", "proxmox/proxmox-admin"],
        input="1\n\ny\nc\n\ny\nq\n",
    )

    assert result.exit_code == 0
    assert settings_snapshots == [{"first"}]
    assert providers == [("home-proxmox", "secret")]
    assert lifecycle.calls == [
        ("first", EnvironmentScope.NONE, False),
        ("second", EnvironmentScope.COURSE, False),
    ]
    assert store.completed_lessons("proxmox", "proxmox-admin") == {
        "first",
        "second",
    }


def test_incompatible_provider_capability_fails_before_config_or_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli

    course = Course(
        collection_id="proxmox",
        id="proxmox-admin",
        title="Unsupported Provider Course",
        lessons=(session_lesson(),),
        environment=EnvironmentPolicy(EnvironmentScope.COURSE, "other.vm"),
    )
    lifecycle = SessionLifecycle()
    store, providers = install_session_cli(
        monkeypatch,
        tmp_xdg,
        course,
        lambda *args, **kwargs: lifecycle,
    )
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: pytest.fail("incompatible capability must fail before config"),
    )
    monkeypatch.setattr(
        cli,
        "resolve_token_secret",
        lambda profile: pytest.fail("incompatible capability must not read a secret"),
    )

    result = CliRunner().invoke(
        cli.app,
        ["start", "proxmox/proxmox-admin"],
        input="\n",
    )

    assert result.exit_code == 3
    assert "Unsupported provider capability: other.vm" in result.stdout
    assert providers == []
    assert lifecycle.calls == []
    assert store.list_attempts() == []
    assert store.list_environments() == []


@pytest.mark.parametrize("command", ["start", "resume"])
def test_start_and_resume_continue_at_first_incomplete_verification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
    command: str,
) -> None:
    from learnlab import cli

    checks = (
        Verification(
            id="already-passed",
            type=VerificationType.MANUAL_CONFIRMATION,
            prompt="Confirm the first result.",
        ),
        Verification(
            id="retry-this",
            type=VerificationType.MANUAL_CONFIRMATION,
            prompt="Confirm the second result.",
            failure_message="Review the output and try again.",
        ),
    )
    lifecycle = SessionLifecycle()
    store, _ = install_session_cli(
        monkeypatch,
        tmp_xdg,
        session_course(
            EnvironmentScope.NONE,
            lessons=(session_lesson(checks=checks),),
        ),
        lambda *args, **kwargs: lifecycle,
    )
    step_path = ("proxmox", "proxmox-admin", "basics", "inspect")
    store.start_lesson("proxmox", "proxmox-admin", "basics")
    store.start_step(step_path)
    store.record_verification_result(
        step_path,
        "already-passed",
        passed=True,
        evidence=None,
        validator_type=VerificationType.MANUAL_CONFIRMATION,
        self_attested=True,
    )

    result = CliRunner().invoke(
        cli.app,
        [command, "proxmox/proxmox-admin"],
        input="\n\nn\nr\ny\nq\n",
    )

    assert result.exit_code == 0
    assert "Verification 1 of 2: already-passed" not in result.stdout
    assert "Verification 2 of 2: retry-this" in result.stdout
    assert "FAIL: Review the output and try again." in result.stdout
    assert "Retry this verification" in result.stdout
    assert "PASS (self-attested): Learner confirmed" in result.stdout
    records = {
        record.verification_id: record
        for record in store.verification_records(step_path)
    }
    assert records["already-passed"].attempt_count == 1
    assert records["retry-this"].attempt_count == 2


def test_completed_lesson_offers_next_lesson_before_returning_to_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli

    lifecycle = SessionLifecycle()
    install_session_cli(
        monkeypatch,
        tmp_xdg,
        session_course(
            EnvironmentScope.NONE,
            lessons=(
                session_lesson("first", "First Lesson"),
                session_lesson("second", "Second Lesson"),
            ),
        ),
        lambda *args, **kwargs: lifecycle,
    )

    result = CliRunner().invoke(
        cli.app,
        ["start", "proxmox/proxmox-admin"],
        input="1\n\ny\nq\n",
    )

    assert result.exit_code == 0
    assert "Lesson complete: First Lesson" in result.stdout
    assert "Next lesson: Second Lesson" in result.stdout
    assert result.stdout.index("Next lesson: Second Lesson") < result.stdout.index(
        "Progress saved."
    )
    assert lifecycle.calls == [("first", EnvironmentScope.NONE, False)]


def test_lesson_replacement_discloses_exact_target_before_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli

    lessons = (
        session_lesson("first", "First Lesson"),
        session_lesson("second", "Second Lesson"),
    )
    course = session_course(EnvironmentScope.LESSON, lessons=lessons)
    store, providers = install_session_cli(
        monkeypatch,
        tmp_xdg,
        course,
        lambda *args, **kwargs: replacement,
    )
    existing = EnvironmentRecord(
        id="env-first",
        collection_id="proxmox",
        course_id="proxmox-admin",
        lesson_id="first",
        attempt_id=None,
        profile_name="home-proxmox",
        provider_type="proxmox",
        phase=EnvironmentPhase.RUNNING,
        vmid=117,
        node="pve",
        provider_endpoint="https://proxmox.example.test:8006",
        provider_fingerprint="test-fingerprint",
        expected_vm_name="learnlab-proxmox-admin-117",
        environment_scope=EnvironmentScope.LESSON,
        lesson_owner_id="first",
    )
    store.create_environment(existing)
    replacement = ReplacementSessionLifecycle(existing)

    result = CliRunner().invoke(
        cli.app,
        ["start", "proxmox/proxmox-admin"],
        input="2\ny\n\ny\nq\n",
    )

    assert result.exit_code == 0
    assert "Existing environment to replace:" in result.stdout
    assert "VM 117" in result.stdout
    assert "learnlab-proxmox-admin-117" in result.stdout
    assert "First Lesson" in result.stdout
    assert "Second Lesson" in result.stdout
    assert replacement.calls == [
        ("second", EnvironmentScope.LESSON, False),
        ("second", EnvironmentScope.LESSON, True),
    ]
    assert providers == [("home-proxmox", "secret")]


def test_start_emits_life_sign_before_blocking_provisioning_returns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli

    entered = threading.Event()
    release = threading.Event()
    output = StringIO()
    result_holder: list[object] = []
    install_session_cli(
        monkeypatch,
        tmp_xdg,
        session_course(EnvironmentScope.COURSE),
        lambda *args, progress, **kwargs: BlockingSessionLifecycle(
            progress, entered, release
        ),
    )
    monkeypatch.setattr(
        cli,
        "progress_renderer_factory",
        lambda: cli.TerminalProgressRenderer(output, is_terminal=False),
    )

    worker = threading.Thread(
        target=lambda: result_holder.append(
            CliRunner().invoke(
                cli.app,
                ["start", "proxmox/proxmox-admin"],
                input="\n\ny\nq\n",
            )
        )
    )
    worker.start()
    assert entered.wait(timeout=2), result_holder

    assert "Creating lesson environment" in output.getvalue()
    assert worker.is_alive()

    release.set()
    worker.join(timeout=3)
    assert not worker.is_alive()
    assert result_holder[0].exit_code == 0


def test_provisioning_interrupt_prints_destroy_guidance_without_resume_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli

    store, _ = install_session_cli(
        monkeypatch,
        tmp_xdg,
        session_course(EnvironmentScope.COURSE),
        lambda *args, **kwargs: ProvisioningInterruptedLifecycle(),
    )

    result = CliRunner().invoke(
        cli.app,
        ["start", "proxmox/proxmox-admin"],
        input="\n",
    )

    assert result.exit_code == 130
    assert PROVISIONING_INTERRUPTED_GUIDANCE in result.stdout
    assert "Progress saved" not in result.stdout
    assert "learnlab resume" not in result.stdout
    assert "secret" not in result.stdout
    assert store.lesson_statuses("proxmox", "proxmox-admin") == {}


def test_replacement_interrupt_prints_destroy_guidance_without_resume_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli

    existing = EnvironmentRecord(
        id="env-first",
        collection_id="proxmox",
        course_id="proxmox-admin",
        lesson_id="first",
        attempt_id=None,
        profile_name="home-proxmox",
        provider_type="proxmox",
        phase=EnvironmentPhase.RUNNING,
        vmid=117,
        node="pve",
        provider_endpoint="https://proxmox.example.test:8006",
        provider_fingerprint="test-fingerprint",
        expected_vm_name="learnlab-proxmox-admin-117",
        environment_scope=EnvironmentScope.LESSON,
        lesson_owner_id="first",
    )
    lifecycle = InterruptedReplacementSessionLifecycle(existing)
    store, _ = install_session_cli(
        monkeypatch,
        tmp_xdg,
        session_course(
            EnvironmentScope.LESSON,
            lessons=(session_lesson("second", "Second Lesson"),),
        ),
        lambda *args, **kwargs: lifecycle,
    )
    store.create_environment(existing)

    result = CliRunner().invoke(
        cli.app,
        ["start", "proxmox/proxmox-admin"],
        input="\ny\n",
    )

    assert result.exit_code == 130
    assert PROVISIONING_INTERRUPTED_GUIDANCE in result.stdout
    assert "learnlab destroy" in result.stdout
    assert "Progress saved" not in result.stdout
    assert "learnlab resume" not in result.stdout
    assert lifecycle.calls == [
        ("second", EnvironmentScope.LESSON, False),
        ("second", EnvironmentScope.LESSON, True),
    ]
    retained = store.get_environment("env-first")
    assert retained is not None
    assert retained.vmid == 117
    assert retained.phase is EnvironmentPhase.RUNNING


def test_continue_emits_life_sign_while_second_lesson_provisioning_blocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli

    second_entered = threading.Event()
    release_second = threading.Event()
    output = StringIO()
    result_holder: list[object] = []
    lifecycle_holder: list[ContinuingBlockingSessionLifecycle] = []
    course = session_course(
        EnvironmentScope.LESSON,
        lessons=(
            session_lesson("first", "First Lesson"),
            session_lesson("second", "Second Lesson"),
        ),
    )

    def lifecycle_factory(*args, progress, **kwargs):
        lifecycle = ContinuingBlockingSessionLifecycle(
            progress,
            second_entered,
            release_second,
        )
        lifecycle_holder.append(lifecycle)
        return lifecycle

    install_session_cli(monkeypatch, tmp_xdg, course, lifecycle_factory)
    monkeypatch.setattr(
        cli,
        "progress_renderer_factory",
        lambda: cli.TerminalProgressRenderer(output, is_terminal=False),
    )

    worker = threading.Thread(
        target=lambda: result_holder.append(
            CliRunner().invoke(
                cli.app,
                ["start", "proxmox/proxmox-admin"],
                input="1\n\ny\nc\n\ny\nq\n",
            )
        )
    )
    worker.start()
    assert second_entered.wait(timeout=2), result_holder

    try:
        assert output.getvalue().count("Creating lesson environment") == 2
        assert worker.is_alive()
    finally:
        release_second.set()
        worker.join(timeout=3)
    assert not worker.is_alive()
    assert result_holder[0].exit_code == 0
    assert lifecycle_holder[0].calls == [
        ("first", EnvironmentScope.LESSON, False),
        ("second", EnvironmentScope.LESSON, False),
    ]


def test_start_resolves_secret_once_and_shares_one_redaction_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
) -> None:
    from learnlab import cli

    secret_calls: list[str] = []
    redaction_sets: list[set[str]] = []
    provider_secrets: list[str | None] = []
    course = session_course(EnvironmentScope.COURSE)
    store = StateStore(tmp_xdg / "shared-secret" / "learnlab.db")
    store.initialize()

    class RecordingSshExecutor:
        def __init__(self, state_path: Path, *, secrets: set[str]) -> None:
            redaction_sets.append(secrets)

    class RecordingSession:
        def __init__(self, **kwargs) -> None:
            redaction_sets.append(kwargs["secrets"])
            self.course = kwargs["course"]
            self.dependency_resolver = kwargs["dependency_resolver"]

        def run(self, **kwargs) -> SessionOutcome:
            self.dependency_resolver.resolve(self.course.environment)
            return SessionOutcome(SessionAction.EXIT, "basics")

    def provider_factory(settings, profile_name: str, secret=None):
        provider_secrets.append(secret)
        return object()

    def lifecycle_factory(*args, secrets: set[str], **kwargs):
        redaction_sets.append(secrets)
        return SessionLifecycle(EnvironmentResolution("created"))

    def resolve_secret(profile) -> str:
        secret_calls.append(profile.name)
        return "one-secret"

    monkeypatch.setattr(cli, "catalog_factory", lambda: RecordingCatalog(course))
    monkeypatch.setattr(cli, "state_store_factory", lambda: store)
    monkeypatch.setattr(cli, "state_root", lambda: tmp_xdg / "shared-secret")
    monkeypatch.setattr(cli, "provider_factory", provider_factory)
    monkeypatch.setattr(cli, "lifecycle_factory", lifecycle_factory)
    monkeypatch.setattr(cli, "resolve_token_secret", resolve_secret)
    monkeypatch.setattr(cli, "SshExecutor", RecordingSshExecutor)
    monkeypatch.setattr(cli, "CourseSession", RecordingSession)

    result = CliRunner().invoke(
        cli.app,
        ["start", "proxmox/proxmox-admin"],
        input="\n",
    )

    assert result.exit_code == 0
    assert secret_calls == ["home-proxmox"]
    assert provider_secrets == ["one-secret"]
    assert len(redaction_sets) == 3
    assert all(item is redaction_sets[0] for item in redaction_sets)
    assert redaction_sets[0] == {"one-secret"}


def test_start_defaults_to_first_incomplete_lesson(app_harness: AppHarness) -> None:
    app_harness.complete("proxmox", "proxmox-admin", "api-access")

    result = app_harness.invoke(
        ["start", "proxmox/proxmox-admin", "--provider", "home-proxmox"],
        input="\nq\n",
    )

    assert result.exit_code == 0
    assert "1. API Access [completed]" in result.stdout
    assert "2. API Tokens [first incomplete]" in result.stdout
    assert app_harness.lifecycle.requests.one().lesson.id == "api-tokens"
    assert "Environment policy: course (proxmox.vm)" in result.stdout
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
        input="1\nq\n",
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
        input="\nq\n",
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
        input="2\n\ny\nq\n",
    )

    assert result.exit_code == 0
    output = result.stdout
    assert output.index("Step 1 of 2: Create a token") < output.index(
        "Create a dedicated API token."
    )
    assert output.index("Create a dedicated API token.") < output.index(
        "Step 2 of 2: Limit the token"
    )
    assert output.index("Step 2 of 2: Limit the token") < output.index(
        "Apply least privilege."
    )


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
        input="1\nq\n",
    )

    assert result.exit_code == 0
    assert "1. API Access [in progress]" in result.stdout


def test_start_uses_default_provider_profile(app_harness: AppHarness) -> None:
    result = app_harness.invoke(
        ["start", "proxmox/proxmox-admin"],
        input="\nq\n",
    )

    assert result.exit_code == 0
    assert app_harness.provider_profiles == ["home-proxmox"]


def test_start_warns_when_tls_verification_is_disabled_before_connection_details(
    app_harness: AppHarness, tmp_xdg: Path
) -> None:
    config = tmp_xdg / "config" / "learnlab" / "config.toml"
    config.write_text(
        CONFIG.replace("tls_verify = true", "tls_verify = false"),
        encoding="utf-8",
    )

    result = app_harness.invoke(["start", "proxmox/proxmox-admin"], input="\nq\n")

    assert result.exit_code == 0
    warning = "WARNING: TLS certificate verification is disabled"
    assert warning in result.stdout
    assert result.stdout.index(warning) < result.stdout.index("Lesson: API Access")


def test_progress_complete_requires_administrative_override_confirmation(
    app_harness: AppHarness,
) -> None:
    cancelled = app_harness.invoke(
        ["progress", "complete", "proxmox/proxmox-admin/api-access"], input="n\n"
    )

    assert cancelled.exit_code == 0
    assert "administrative override" in cancelled.stdout
    assert app_harness.store.completed_lessons("proxmox", "proxmox-admin") == set()

    confirmed = app_harness.invoke(
        ["progress", "complete", "proxmox/proxmox-admin/api-access"], input="y\n"
    )

    assert confirmed.exit_code == 0
    assert "Normal learners should complete lessons through start or resume" in (
        confirmed.stdout
    )
    assert (
        app_harness.store.lesson_completion_source(
            ("proxmox", "proxmox-admin", "api-access")
        )
        is CompletionSource.MANUAL_OVERRIDE
    )


def test_progress_complete_yes_advances_later_start_default(
    app_harness: AppHarness,
) -> None:
    completed = app_harness.invoke(
        ["progress", "complete", "proxmox/proxmox-admin/api-access", "--yes"]
    )
    started = app_harness.invoke(
        ["start", "proxmox/proxmox-admin"],
        input="\nq\n",
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
    assert "Endpoint: https://proxmox.example.test:8006" in result.stdout
    assert "Fingerprint: test-provider-fingerprint" in result.stdout
    assert "Expected VM name: learnlab-proxmox-admin-102" in result.stdout
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


def test_destroy_shows_tls_warning_and_endpoint_before_confirmation(
    app_harness: AppHarness, tmp_xdg: Path
) -> None:
    config = tmp_xdg / "config" / "learnlab" / "config.toml"
    config.write_text(
        CONFIG.replace("tls_verify = true", "tls_verify = false"),
        encoding="utf-8",
    )
    app_harness.seed_environment(vmid=102)

    result = app_harness.invoke(["destroy"], input="n\n")

    warning = "WARNING: TLS certificate verification is disabled"
    assert result.exit_code == 0
    assert "Configured endpoint: https://proxmox.example.test:8006" in result.stdout
    assert result.stdout.index(warning) < result.stdout.index(
        "Destroy all listed environments?"
    )


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
    app_harness.store.transition_environment(
        "env-102",
        EnvironmentPhase.FAILED,
        error_summary="ownership fingerprint mismatch",
    )

    result = app_harness.invoke(["destroy", "--yes", "--preserve-progress"])

    assert result.exit_code == 3
    assert "Retained environment: env-102" in result.stdout
    assert "VM 102" in result.stdout
    assert "Error: ownership fingerprint mismatch" in result.stdout


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


def test_validate_all_is_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    from learnlab import cli

    def forbidden(*args, **kwargs):
        pytest.fail("offline validation must not access runtime dependencies")

    for dependency in (
        "load_settings",
        "load_requested_profiles",
        "resolve_token_secret",
        "state_store_factory",
        "provider_factory",
        "lifecycle_factory",
        "validator_registry_factory",
        "SshExecutor",
    ):
        monkeypatch.setattr(cli, dependency, forbidden)

    result = CliRunner().invoke(cli.app, ["validate"])

    assert result.exit_code == 0
    assert "WARNING" in result.stdout


def test_validate_json_is_versioned_deterministic_and_matches_snapshot() -> None:
    from learnlab.cli import app

    first = CliRunner().invoke(app, ["validate", "--format", "json"])
    second = CliRunner().invoke(app, ["validate", "--format", "json"])

    assert first.exit_code == 0
    assert first.stdout == second.stdout
    assert first.stdout == (SNAPSHOTS / "validate-report-v1.json").read_text(
        encoding="utf-8"
    )
    payload = json.loads(first.stdout)
    assert tuple(payload) == ("schema_version", "ok", "findings")
    assert payload["schema_version"] == 1
    assert payload["ok"] is True


def test_validate_one_unknown_well_formed_course_is_a_finding() -> None:
    from learnlab.cli import app

    result = CliRunner().invoke(app, ["validate", "demo/unknown"])

    assert result.exit_code == 1
    assert "ERROR" in result.stdout
    assert "demo/unknown" in result.stdout
    assert "invalid-curriculum" in result.stdout
    assert "Remedy:" in result.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        ["validate", "demo"],
        ["validate", "demo/course/extra"],
        ["validate", "Demo/course"],
        ["validate", "--format", "yaml"],
        ["validate", "demo/course", "unexpected"],
    ],
)
def test_validate_rejects_invalid_command_usage(arguments: list[str]) -> None:
    from learnlab.cli import app

    result = CliRunner().invoke(app, arguments)

    assert result.exit_code == 2


def test_validate_human_output_has_deterministic_actionable_fields() -> None:
    from learnlab.cli import app

    first = CliRunner().invoke(app, ["validate"])
    second = CliRunner().invoke(app, ["validate"])

    assert first.exit_code == 0
    assert first.stdout == second.stdout
    assert "WARNING deprecated-requirements" in first.stdout
    assert "Course: proxmox/proxmox-admin" in first.stdout
    assert "Source: proxmox/courses/proxmox-admin/course.yaml" in first.stdout
    assert "Message:" in first.stdout
    assert "Remedy:" in first.stdout
    assert str(Path.cwd()) not in first.stdout


def test_validate_provider_loads_only_requested_profile_and_calls_only_health(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from learnlab import cli
    from learnlab.config import ProxmoxProfile, RequestedProfiles, Settings

    profile = ProxmoxProfile(
        "lab", "https://example.test", "token", "SECRET", 9000, "template",
        "node", "storage", "vmbr0", "student", tmp_path / "key", True,
        ("proxmox.api",),
    )
    settings = Settings("lab", MappingProxyType({"lab": profile}))
    calls: list[object] = []

    class ReadOnlyProvider:
        def health_check(self) -> ProviderHealth:
            calls.append("health_check")
            return ProviderHealth((ProviderCheck("API", True, "reachable"),))

        def __getattr__(self, name: str):
            pytest.fail(f"validation accessed provider operation {name}")

    def load_profiles(names):
        calls.append(tuple(names))
        return RequestedProfiles(settings, MappingProxyType({}))

    monkeypatch.setattr(cli, "load_requested_profiles", load_profiles)
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: pytest.fail("must load requested only"),
    )
    monkeypatch.setattr(cli, "resolve_token_secret", lambda selected: "resolved-secret")
    monkeypatch.setattr(
        cli,
        "provider_factory",
        lambda selected, name, secret: (
            calls.append((selected, name, secret)) or ReadOnlyProvider()
        ),
    )

    result = CliRunner().invoke(
        cli.app, ["validate", "proxmox/proxmox-admin", "--provider", "lab"]
    )

    assert result.exit_code == 0
    assert calls == [
        ("lab",),
        (settings, "lab", "resolved-secret"),
        "health_check",
    ]


def test_validate_provider_stops_after_offline_errors_and_json_reports_not_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from learnlab import cli

    monkeypatch.setattr(
        cli,
        "load_requested_profiles",
        lambda names: pytest.fail("offline errors must prevent provider access"),
    )

    result = CliRunner().invoke(
        cli.app,
        ["validate", "demo/unknown", "--provider", "lab", "--format", "json"],
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout)["ok"] is False


def test_validate_provider_health_failure_is_safe_json_and_exit_three(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from learnlab import cli
    from learnlab.config import ProxmoxProfile, RequestedProfiles, Settings

    sensitive_value = "SUPER-SECRET-provider-payload"
    profile = ProxmoxProfile(
        "lab", "https://example.test", "token", "SECRET", 9000, "template",
        "node", "storage", "vmbr0", "student", tmp_path / "key", True,
        ("proxmox.api",),
    )
    settings = Settings("lab", MappingProxyType({"lab": profile}))
    monkeypatch.setattr(
        cli,
        "load_requested_profiles",
        lambda names: RequestedProfiles(settings, MappingProxyType({})),
    )
    monkeypatch.setattr(
        cli, "resolve_token_secret", lambda selected: sensitive_value
    )
    monkeypatch.setattr(
        cli,
        "provider_factory",
        lambda settings, name, resolved: FailedHealthProvider(
            ProviderHealth(
                (ProviderCheck("Authentication", False, sensitive_value),),
                warnings=(sensitive_value,),
                provider_error=True,
            )
        ),
    )

    result = CliRunner().invoke(
        cli.app,
        ["validate", "proxmox/proxmox-admin", "--provider", "lab", "--format", "json"],
    )

    assert result.exit_code == 3
    payload = json.loads(result.stdout)
    assert tuple(payload) == ("schema_version", "ok", "findings")
    assert payload["ok"] is False
    assert sensitive_value not in result.stdout
    assert payload["findings"][0]["code"] == "provider-health-failed"


def test_validate_rejects_empty_provider_name_as_usage_error() -> None:
    from learnlab.cli import app

    result = CliRunner().invoke(app, ["validate", "--provider", ""])

    assert result.exit_code == 2


@pytest.mark.parametrize(
    "failure_stage",
    ["profile", "secret", "provider", "health"],
)
def test_validate_provider_operational_exceptions_are_redacted_and_exit_three(
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
    tmp_path: Path,
) -> None:
    from learnlab import cli
    from learnlab.config import ProxmoxProfile, RequestedProfiles, Settings
    from learnlab.errors import ConfigurationError, ProviderError

    sensitive_value = f"SUPER-SECRET-{failure_stage}"
    profile = ProxmoxProfile(
        "lab", "https://example.test", "token", "SECRET", 9000, "template",
        "node", "storage", "vmbr0", "student", tmp_path / "key", True,
        ("proxmox.api",),
    )
    settings = Settings("lab", MappingProxyType({"lab": profile}))

    def fail(error_type):
        raise error_type(sensitive_value)

    if failure_stage == "profile":
        loaded = RequestedProfiles(
            Settings("", MappingProxyType({})),
            MappingProxyType({"lab": ConfigurationError(sensitive_value)}),
        )
    else:
        loaded = RequestedProfiles(settings, MappingProxyType({}))
    monkeypatch.setattr(cli, "load_requested_profiles", lambda names: loaded)
    monkeypatch.setattr(
        cli,
        "resolve_token_secret",
        lambda selected: fail(ConfigurationError)
        if failure_stage == "secret"
        else sensitive_value,
    )

    class HealthProvider:
        def health_check(self) -> ProviderHealth:
            if failure_stage == "health":
                fail(ProviderError)
            return ProviderHealth(())

    monkeypatch.setattr(
        cli,
        "provider_factory",
        lambda selected, name, secret: fail(ProviderError)
        if failure_stage == "provider"
        else HealthProvider(),
    )

    result = CliRunner().invoke(
        cli.app,
        ["validate", "proxmox/proxmox-admin", "--provider", "lab", "--format", "json"],
    )

    assert result.exit_code == 3
    assert sensitive_value not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["findings"][0]["code"] == "provider-validation-failed"


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


def test_reset_collection_counts_progress_preserved_after_destroy(
    app_harness: AppHarness,
) -> None:
    app_harness.store.complete_lesson("proxmox", "proxmox-admin", "api-access")

    result = app_harness.invoke(["reset", "proxmox"], input="n\n")

    assert result.exit_code == 0
    assert "Affected courses: 1" in result.stdout
    assert "Affected lessons: 1" in result.stdout
    assert "Cancelled." in result.stdout


def test_default_database_name_is_learnlab_db(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from learnlab import cli

    monkeypatch.setattr(cli, "state_root", lambda: tmp_path)

    assert cli._default_state_store().db_path == tmp_path / "learnlab.db"


def test_start_migrates_legacy_default_db_and_resumes_active_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from learnlab import cli

    state_root_path = tmp_path / "state" / "learnlab"
    legacy_path = state_root_path / "state.db"
    _create_pre_ownership_legacy_db(legacy_path)
    provider_calls: list[str] = []
    lifecycle_calls: list[str] = []
    config_dir = tmp_path / "config" / "learnlab"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("LEARNLAB_HOME_SECRET", "secret")
    monkeypatch.setattr(cli, "state_root", lambda: state_root_path)
    monkeypatch.setattr(
        cli,
        "provider_factory",
        lambda *args, **kwargs: provider_calls.append("provider") or object(),
    )
    monkeypatch.setattr(
        cli,
        "lifecycle_factory",
        lambda *args, **kwargs: (
            lifecycle_calls.append("lifecycle")
            or SessionLifecycle(EnvironmentResolution("reused"))
        ),
    )

    result = CliRunner().invoke(
        cli.app,
        ["start", "proxmox/proxmox-admin"],
        input="\nq\n",
    )

    current_path = state_root_path / "learnlab.db"
    backup_path = state_root_path / "state.db.migrated"
    assert result.exit_code == 0
    assert "already has an environment" not in result.stdout
    assert provider_calls == ["provider"]
    assert lifecycle_calls == ["lifecycle"]
    assert current_path.exists()
    assert not legacy_path.exists()
    assert backup_path.exists()
    assert cli._default_state_store().db_path == current_path

    migrated = StateStore(current_path)
    assert migrated.completed_lessons("proxmox", "proxmox-admin") == {"api-access"}
    [attempt] = migrated.list_attempts()
    [environment] = migrated.list_environments()
    assert attempt.id == "attempt-legacy"
    assert environment.id == "env-legacy"
    assert environment.phase is EnvironmentPhase.RUNNING
    assert environment.provider_endpoint == ""
    assert environment.provider_fingerprint == ""
    assert environment.expected_vm_name == ""

    with sqlite3.connect(current_path) as connection:
        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(environments)")
        }
    assert {
        "provider_endpoint",
        "provider_fingerprint",
        "expected_vm_name",
        "clone_uncertain",
    } <= columns
    with sqlite3.connect(backup_path) as connection:
        assert connection.execute("SELECT id FROM attempts").fetchall() == [
            ("attempt-legacy",)
        ]
        assert connection.execute("SELECT id FROM environments").fetchall() == [
            ("env-legacy",)
        ]
        backup_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(environments)")
        }
    assert "provider_fingerprint" not in backup_columns


@pytest.mark.parametrize(
    ("arguments", "user_input"),
    [
        (["start", "proxmox/proxmox-admin"], "\n"),
        (["destroy", "--yes", "--preserve-progress"], None),
        (["reset", "proxmox/proxmox-admin", "--yes"], None),
        (["progress", "complete", "proxmox/proxmox-admin/api-access"], None),
    ],
)
def test_state_commands_fail_closed_when_both_default_databases_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg: Path,
    arguments: list[str],
    user_input: str | None,
) -> None:
    from learnlab import cli

    state_root_path = tmp_xdg / "state" / "learnlab"
    legacy_path = state_root_path / "state.db"
    current_path = state_root_path / "learnlab.db"
    legacy = StateStore(legacy_path)
    current = StateStore(current_path)
    legacy.initialize()
    current.initialize()
    legacy.start_lesson("legacy", "legacy-course", "legacy-lesson")
    current.complete_lesson("current", "current-course", "current-lesson")
    external_calls: list[str] = []
    monkeypatch.setenv("LEARNLAB_HOME_SECRET", "secret")
    monkeypatch.setattr(cli, "state_root", lambda: state_root_path)
    monkeypatch.setattr(
        cli,
        "provider_factory",
        lambda *args, **kwargs: external_calls.append("provider"),
    )
    monkeypatch.setattr(
        cli,
        "lifecycle_factory",
        lambda *args, **kwargs: external_calls.append("lifecycle"),
    )

    result = CliRunner().invoke(cli.app, arguments, input=user_input)

    assert result.exit_code == 3
    assert str(legacy_path) in result.stdout
    assert str(current_path) in result.stdout
    assert "manual recovery" in result.stdout
    assert "leave exactly one" in result.stdout
    assert external_calls == []
    assert legacy.lesson_statuses("legacy", "legacy-course") == {
        "legacy-lesson": ProgressStatus.IN_PROGRESS
    }
    assert current.lesson_statuses("current", "current-course") == {
        "current-lesson": ProgressStatus.COMPLETED
    }


def test_legacy_default_migration_includes_committed_active_wal_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from learnlab import cli

    state_root_path = tmp_path / "state" / "learnlab"
    legacy_path = state_root_path / "state.db"
    StateStore(legacy_path).initialize()
    writer = sqlite3.connect(legacy_path)
    try:
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute(
            """
            INSERT INTO progress (
                collection_id, course_id, lesson_id, status, created_at, updated_at
            ) VALUES (
                'proxmox', 'proxmox-admin', 'api-access', 'completed',
                '2026-08-29T00:00:00Z', '2026-08-29T00:00:00Z'
            )
            """
        )
        writer.commit()
        wal_path = legacy_path.with_name(f"{legacy_path.name}-wal")
        assert wal_path.exists()
        assert wal_path.stat().st_size > 0
        main_only_copy = tmp_path / "main-only.db"
        shutil.copyfile(legacy_path, main_only_copy)
        with sqlite3.connect(main_only_copy) as connection:
            assert connection.execute("SELECT * FROM progress").fetchall() == []

        monkeypatch.setattr(cli, "state_root", lambda: state_root_path)
        result = CliRunner().invoke(
            cli.app,
            ["reset", "proxmox/proxmox-admin"],
            input="n\n",
        )

        assert result.exit_code == 0
        assert "Affected lessons: 1" in result.stdout
        assert "Cancelled." in result.stdout
        current = StateStore(state_root_path / "learnlab.db")
        assert current.completed_lessons("proxmox", "proxmox-admin") == {"api-access"}
        with sqlite3.connect(state_root_path / "state.db.migrated") as connection:
            assert connection.execute(
                "SELECT lesson_id, status FROM progress"
            ).fetchall() == [("api-access", "completed")]
    finally:
        writer.close()


@pytest.mark.parametrize(
    "artifact_names",
    [
        (".learnlab.db.migrating",),
        (".learnlab.db.migrating-wal",),
        (".learnlab.db.migrating-journal",),
        ("state.db-wal",),
        ("state.db.migrated",),
        ("state.db", "state.db.migrated"),
    ],
)
def test_default_state_store_refuses_ambiguous_migration_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    artifact_names: tuple[str, ...],
) -> None:
    from learnlab import cli

    state_root_path = tmp_path / "state" / "learnlab"
    state_root_path.mkdir(parents=True)
    for artifact_name in artifact_names:
        (state_root_path / artifact_name).write_bytes(b"retained for recovery")
    monkeypatch.setattr(cli, "state_root", lambda: state_root_path)

    with pytest.raises(StateConflictError, match="manual recovery"):
        cli._default_state_store()


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


def _create_pre_ownership_legacy_db(path: Path) -> None:
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE progress (
                collection_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (collection_id, course_id, lesson_id)
            );
            CREATE TABLE attempts (
                id TEXT PRIMARY KEY,
                collection_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE environments (
                id TEXT PRIMARY KEY,
                collection_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                attempt_id TEXT,
                profile_name TEXT NOT NULL,
                provider_type TEXT NOT NULL,
                vmid INTEGER,
                node TEXT,
                ip_address TEXT,
                phase TEXT NOT NULL,
                upid TEXT,
                error_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO progress VALUES (
                'proxmox', 'proxmox-admin', 'api-access', 'completed',
                '2026-08-29T00:00:00Z', '2026-08-29T00:00:00Z'
            );
            INSERT INTO attempts VALUES (
                'attempt-legacy', 'proxmox', 'proxmox-admin', 'api-access',
                '2026-08-29T00:00:00Z'
            );
            INSERT INTO environments VALUES (
                'env-legacy', 'proxmox', 'proxmox-admin', 'api-access',
                'attempt-legacy', 'home-proxmox', 'proxmox', 102, 'pve02',
                '192.0.2.10', 'running', 'UPID:start', NULL,
                '2026-08-29T00:00:00Z', '2026-08-29T00:00:00Z'
            );
            """
        )
