from __future__ import annotations

import sqlite3
import stat
import subprocess
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pytest
from typer.testing import CliRunner

from learnlab.config import state_dir
from learnlab.curriculum import (
    Course,
    EnvironmentPolicy,
    EnvironmentScope,
    Lesson,
    Step,
    Verification,
    VerificationType,
)
from learnlab.providers.base import ProviderCheck, ProviderHealth, VmLocation
from learnlab.ssh import SshExecutor
from learnlab.state import (
    CompletionSource,
    StateStore,
    VerificationStatus,
    resolve_default_state_db,
)

COURSE_PATH = "fake/full-course"
SECRET = "integration-token-secret"  # noqa: S105 - deliberate redaction sentinel
HOST_KEY = "192.0.2.44 ssh-ed25519 aG9zdC1wdWJsaWMta2V5"
HOST_FINGERPRINT = "SHA256:hXBw+k0I59jZzDV4ZC5NNDnXbG6HjQJobltlAdMlBms"
CONFIG = """
default_provider = "fake-provider"

[providers.fake-provider]
type = "proxmox"
api_url = "https://provider.example.test:8006"
token_id = "learnlab@pam!integration"
token_secret_env = "LEARNLAB_INTEGRATION_SECRET"
template_vmid = 9001
template_name = "debian-12-learning"
node = "pve"
storage = "local-lvm"
network = "vmbr0"
ssh_user = "student"
ssh_identity_file = "/keys/learnlab-integration"
tls_verify = true
"""


class FakeCatalog:
    def __init__(self, course: Course) -> None:
        self.course = course

    def load_course(self, course_path: str) -> Course:
        assert course_path == COURSE_PATH
        return self.course


@dataclass
class FakeVm:
    name: str
    status: str


class FakeProvider:
    """Stateful provider boundary fake shared by all public CLI invocations."""

    def __init__(
        self,
        vmids: tuple[int, ...],
        *,
        block_first_allocation: bool = False,
    ) -> None:
        self.api_origin = "https://provider.example.test:8006"
        self.profile_fingerprint = ""
        self.operations: list[str] = []
        self.vms: dict[int, FakeVm] = {}
        self._vmids = iter(vmids)
        self._check_results: dict[str, deque[ProviderCheck]] = {}
        self._block_first_allocation = block_first_allocation
        self._has_blocked = False
        self.allocation_entered = threading.Event()
        self.release_allocation = threading.Event()

    def set_check_results(self, check: str, *results: ProviderCheck) -> None:
        self._check_results[check] = deque(results)

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(())

    def run_check(self, check: str, environment) -> ProviderCheck:
        vmid = environment.vmid if environment is not None else None
        self.operations.append(f"check:{check}:{vmid}")
        return self._check_results[check].popleft()

    def allocate_vmid(self) -> int:
        vmid = next(self._vmids)
        self.operations.append(f"allocate:{vmid}")
        if self._block_first_allocation and not self._has_blocked:
            self._has_blocked = True
            self.allocation_entered.set()
            if not self.release_allocation.wait(timeout=5):
                raise AssertionError("test did not release fake allocation")
        return vmid

    def clone(self, vmid: int, name: str) -> str:
        self.operations.append(f"clone:{vmid}:{name}")
        self.vms[vmid] = FakeVm(name, "stopped")
        return f"clone-{vmid}"

    def wait_for_task(
        self,
        node: str,
        upid: str,
        timeout: float,
        heartbeat: Callable[[int], None] | None = None,
    ) -> None:
        self.operations.append(f"wait:{upid}")
        if heartbeat is not None:
            heartbeat(1)

    def locate_vm(self, vmid: int) -> VmLocation | None:
        self.operations.append(f"locate:{vmid}")
        vm = self.vms.get(vmid)
        if vm is None:
            return None
        return VmLocation(node="pve", status=vm.status, name=vm.name)

    def start(self, vmid: int, node: str) -> str:
        self.operations.append(f"start:{vmid}")
        self.vms[vmid].status = "running"
        return f"start-{vmid}"

    def stop(self, vmid: int, node: str) -> str:
        self.operations.append(f"stop:{vmid}")
        self.vms[vmid].status = "stopped"
        return f"stop-{vmid}"

    def wait_for_ipv4(
        self,
        vmid: int,
        node: str,
        timeout: float,
        heartbeat: Callable[[int], None] | None = None,
        guest_agent_heartbeat: Callable[[int], None] | None = None,
        address_heartbeat: Callable[[int], None] | None = None,
    ) -> str:
        self.operations.append(f"address:{vmid}")
        if guest_agent_heartbeat is not None:
            guest_agent_heartbeat(1)
        if address_heartbeat is not None:
            address_heartbeat(1)
        return "192.0.2.44"

    def delete(self, vmid: int, node: str) -> str:
        self.operations.append(f"delete:{vmid}")
        del self.vms[vmid]
        return f"delete-{vmid}"


class FakeSshRunner:
    def __init__(self, operations: list[str]) -> None:
        self.operations = operations
        self.results: dict[str, deque[tuple[int, bytes, bytes]]] = {}

    def set_results(self, command: str, *results: tuple[int, bytes, bytes]) -> None:
        self.results[command] = deque(results)

    def __call__(self, argv: list[str], **kwargs: object):
        if argv[0] == "ssh-keyscan":
            target = argv[-1]
            self.operations.append(f"ssh-keyscan:{target}")
            return subprocess.CompletedProcess(argv, 0, f"{HOST_KEY}\n".encode(), b"")
        command = argv[-1]
        self.operations.append(f"ssh:{command}")
        known_hosts_option = next(
            value for value in argv if value.startswith("UserKnownHostsFile=")
        )
        known_hosts = Path(known_hosts_option.partition("=")[2])
        if known_hosts.read_text(encoding="utf-8") != f"{HOST_KEY}\n":
            return subprocess.CompletedProcess(
                argv, 255, b"", b"strict host-key verification failed"
            )
        return_code, stdout, stderr = self.results[command].popleft()
        return subprocess.CompletedProcess(argv, return_code, stdout, stderr)


class FlushPublishingStream:
    """Expose writes only after the renderer explicitly flushes them."""

    def __init__(self) -> None:
        self._staged = StringIO()
        self._published = StringIO()

    def write(self, value: str) -> int:
        return self._staged.write(value)

    def flush(self) -> None:
        self._published.write(self._staged.getvalue())
        self._staged = StringIO()

    def getvalue(self) -> str:
        return self._published.getvalue()


@pytest.fixture
def isolated_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    roots = {
        "XDG_CONFIG_HOME": tmp_path / "config",
        "XDG_STATE_HOME": tmp_path / "state",
        "XDG_DATA_HOME": tmp_path / "data",
        "XDG_CACHE_HOME": tmp_path / "cache",
    }
    for variable, path in roots.items():
        monkeypatch.setenv(variable, str(path))
    config_dir = roots["XDG_CONFIG_HOME"] / "learnlab"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv("LEARNLAB_INTEGRATION_SECRET", SECRET)
    return tmp_path


def full_course() -> Course:
    first_step = Step(
        id="prove-system",
        title="Prove the system",
        instructions="Run the ordered checks.",
        verifications=(
            Verification(
                id="system-ready",
                type=VerificationType.REMOTE_COMMAND,
                command="check-system",
                timeout_seconds=10,
                failure_message="System is not ready yet.",
            ),
            Verification(
                id="service-ready",
                type=VerificationType.REMOTE_COMMAND,
                command="check-service",
                timeout_seconds=10,
            ),
            Verification(
                id="agent-ready",
                type=VerificationType.PROVIDER_CHECK,
                check="guest-agent-ready",
            ),
            Verification(
                id="vm-visible",
                type=VerificationType.PROVIDER_CHECK,
                check="vm-running",
            ),
        ),
    )
    second_step = Step(
        id="reuse-system",
        title="Reuse the system",
        instructions="Prove the same machine remains available.",
        verifications=(
            Verification(
                id="same-system",
                type=VerificationType.REMOTE_COMMAND,
                command="check-reused-system",
                timeout_seconds=10,
            ),
        ),
    )
    return Course(
        collection_id="fake",
        id="full-course",
        title="Fake Full Course",
        lessons=(
            Lesson(id="first", title="First Lesson", steps=(first_step,)),
            Lesson(id="second", title="Second Lesson", steps=(second_step,)),
        ),
        environment=EnvironmentPolicy(EnvironmentScope.COURSE, "proxmox.vm"),
    )


def simple_lesson(lesson_id: str, title: str) -> Lesson:
    return Lesson(
        id=lesson_id,
        title=title,
        steps=(
            Step(
                id="confirm-work",
                title="Confirm the work",
                instructions="Confirm the safe fake operation.",
                verifications=(
                    Verification(
                        id="confirmed",
                        type=VerificationType.MANUAL_CONFIRMATION,
                        prompt="Confirm the work.",
                    ),
                ),
            ),
        ),
    )


def two_lesson_course(scope: EnvironmentScope) -> Course:
    return Course(
        collection_id="fake",
        id="full-course",
        title="Fake Scoped Course",
        lessons=(
            simple_lesson("first", "First Lesson"),
            simple_lesson("second", "Second Lesson"),
        ),
        environment=EnvironmentPolicy(scope, "proxmox.vm"),
    )


def install_public_cli_fakes(
    monkeypatch: pytest.MonkeyPatch,
    course: Course,
    provider: FakeProvider,
    ssh_runner: FakeSshRunner,
    *,
    progress_output: FlushPublishingStream | None = None,
) -> None:
    from learnlab import cli

    monkeypatch.setattr(cli, "catalog_factory", lambda: FakeCatalog(course))

    def provider_factory(settings, profile_name: str, secret: str | None = None):
        profile = settings.provider(profile_name)
        provider.api_origin = profile.api_url
        provider.profile_fingerprint = profile.fingerprint
        return provider

    monkeypatch.setattr(cli, "provider_factory", provider_factory)
    monkeypatch.setattr(
        cli,
        "SshExecutor",
        lambda root, *, secrets=None: SshExecutor(
            root, runner=ssh_runner, secrets=secrets
        ),
    )
    if progress_output is not None:
        monkeypatch.setattr(
            cli,
            "progress_renderer_factory",
            lambda: cli.TerminalProgressRenderer(progress_output, is_terminal=False),
        )


def test_public_course_workflow_resumes_reuses_and_preserves_validated_state(
    monkeypatch: pytest.MonkeyPatch,
    isolated_xdg: Path,
) -> None:
    from learnlab import cli

    provider = FakeProvider((104,), block_first_allocation=True)
    provider.set_check_results(
        "guest-agent-ready",
        ProviderCheck("guest-agent-ready", False, f"agent missing: {SECRET}"),
        ProviderCheck("guest-agent-ready", True, "agent ready"),
    )
    provider.set_check_results(
        "vm-running", ProviderCheck("vm-running", True, "vm running")
    )
    ssh_runner = FakeSshRunner(provider.operations)
    ssh_runner.set_results(
        "check-system",
        (1, b"", f"not ready: {SECRET}".encode()),
        (0, b"system ready", b""),
    )
    ssh_runner.set_results("check-service", (0, b"service ready", b""))
    ssh_runner.set_results("check-reused-system", (0, b"same system", b""))
    progress_output = FlushPublishingStream()
    install_public_cli_fakes(
        monkeypatch,
        full_course(),
        provider,
        ssh_runner,
        progress_output=progress_output,
    )

    results: list[object] = []
    worker = threading.Thread(
        target=lambda: results.append(
            CliRunner().invoke(
                cli.app,
                ["start", COURSE_PATH],
                input="\n\ny\nr\n\n\nr\nq\n",
            )
        )
    )
    worker.start()
    assert provider.allocation_entered.wait(timeout=2), results

    assert progress_output.getvalue() == (
        "Creating lesson environment\nAllocating a virtual machine ID\n"
    )
    assert worker.is_alive()

    provider.release_allocation.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    start_result = results[0]
    assert start_result.exit_code == 0
    assert "FAIL: System is not ready yet." in start_result.stdout
    assert "FAIL: agent missing: [REDACTED]" in start_result.stdout
    assert "Verification 4 of 4: vm-visible" in start_result.stdout
    assert "SSH target: student@192.0.2.44" in start_result.stdout
    assert f"Presented host key: ssh-ed25519 {HOST_FINGERPRINT}" in start_result.stdout
    assert "Strict connection command: ssh -i /keys/learnlab-integration" in (
        start_result.stdout
    )
    assert "Progress saved." in start_result.stdout

    db_path = resolve_default_state_db(state_dir())
    assert db_path == isolated_xdg / "state" / "learnlab" / "learnlab.db"
    store = StateStore(db_path)
    environment = store.active_environment("fake", "full-course")
    assert environment is not None
    assert environment.vmid == 104
    known_hosts = (
        isolated_xdg
        / "state"
        / "learnlab"
        / "environments"
        / environment.id
        / "known_hosts"
    )
    assert stat.S_IMODE(known_hosts.stat().st_mode) == 0o600
    assert known_hosts.read_text(encoding="utf-8") == f"{HOST_KEY}\n"
    cursor = store.session_cursor(("fake", "full-course"))
    assert cursor is not None
    assert (cursor.lesson_id, cursor.step_id, cursor.verification_id) == (
        "first",
        "prove-system",
        "vm-visible",
    )

    resume_result = CliRunner().invoke(
        cli.app,
        ["resume", COURSE_PATH],
        input="\n\nc\n\nq\n",
    )

    assert resume_result.exit_code == 0
    assert "Verification 1 of 4: system-ready" not in resume_result.stdout
    assert "Verification 2 of 4: service-ready" not in resume_result.stdout
    assert "Verification 3 of 4: agent-ready" not in resume_result.stdout
    assert "Verification 4 of 4: vm-visible" in resume_result.stdout
    assert "Lesson complete: First Lesson" in resume_result.stdout
    assert "Lesson: Second Lesson" in resume_result.stdout
    assert "Course complete." in resume_result.stdout
    assert store.completed_lessons("fake", "full-course") == {"first", "second"}
    assert (
        store.lesson_completion_source(("fake", "full-course", "first"))
        is CompletionSource.VALIDATED
    )
    assert (
        store.lesson_completion_source(("fake", "full-course", "second"))
        is CompletionSource.VALIDATED
    )

    destroy_result = CliRunner().invoke(
        cli.app,
        ["destroy", "--yes", "--preserve-progress"],
    )

    assert destroy_result.exit_code == 0
    assert "Destroyed environments: 1" in destroy_result.stdout
    assert provider.operations == [
        "allocate:104",
        "clone:104:learnlab-full-course-104",
        "wait:clone-104",
        "locate:104",
        "start:104",
        "wait:start-104",
        "address:104",
        "ssh-keyscan:192.0.2.44",
        "ssh-keyscan:192.0.2.44",
        "ssh:check-system",
        "ssh:check-system",
        "ssh:check-service",
        "check:guest-agent-ready:104",
        "check:guest-agent-ready:104",
        "locate:104",
        "check:vm-running:104",
        "locate:104",
        "ssh:check-reused-system",
        "locate:104",
        "stop:104",
        "wait:stop-104",
        "delete:104",
        "wait:delete-104",
        "locate:104",
    ]
    assert store.list_environments() == []
    assert store.list_attempts() == []
    assert store.session_cursor(("fake", "full-course")) is None
    assert not known_hosts.exists()

    first_records = {
        record.verification_id: record
        for record in store.verification_records(
            ("fake", "full-course", "first", "prove-system")
        )
    }
    assert {
        verification_id: (record.status, record.attempt_count)
        for verification_id, record in first_records.items()
    } == {
        "system-ready": (VerificationStatus.PASSED, 2),
        "service-ready": (VerificationStatus.PASSED, 1),
        "agent-ready": (VerificationStatus.PASSED, 2),
        "vm-visible": (VerificationStatus.PASSED, 1),
    }
    with sqlite3.connect(db_path) as connection:
        progress_rows = connection.execute(
            "SELECT lesson_id, status, completion_source FROM progress "
            "ORDER BY lesson_id"
        ).fetchall()
        verification_count = connection.execute(
            "SELECT count(*) FROM verification_progress WHERE status = 'passed'"
        ).fetchone()
        step_rows = connection.execute(
            "SELECT lesson_id, step_id, status, completed_at IS NOT NULL "
            "FROM step_progress ORDER BY lesson_id, step_id"
        ).fetchall()
    assert progress_rows == [
        ("first", "completed", "validated"),
        ("second", "completed", "validated"),
    ]
    assert verification_count == (5,)
    assert step_rows == [
        ("first", "prove-system", "completed", 1),
        ("second", "reuse-system", "completed", 1),
    ]

    combined_output = (
        progress_output.getvalue()
        + start_result.output
        + resume_result.output
        + destroy_result.output
    )
    assert SECRET not in combined_output
    assert "[REDACTED]" in combined_output


def test_lesson_scope_confirms_owned_vm_destruction_before_replacement(
    monkeypatch: pytest.MonkeyPatch,
    isolated_xdg: Path,
) -> None:
    from learnlab import cli

    provider = FakeProvider((201, 202))
    ssh_runner = FakeSshRunner(provider.operations)
    install_public_cli_fakes(
        monkeypatch,
        two_lesson_course(EnvironmentScope.LESSON),
        provider,
        ssh_runner,
    )

    first_result = CliRunner().invoke(
        cli.app,
        ["start", COURSE_PATH],
        input="\n\ny\nq\n",
    )

    assert first_result.exit_code == 0
    store = StateStore(resolve_default_state_db(state_dir()))
    first_environment = store.active_environment("fake", "full-course")
    assert first_environment is not None
    first_known_hosts = (
        isolated_xdg
        / "state"
        / "learnlab"
        / "environments"
        / first_environment.id
        / "known_hosts"
    )
    assert first_known_hosts.exists()

    second_result = CliRunner().invoke(
        cli.app,
        ["start", COURSE_PATH],
        input="2\ny\n\ny\nq\n",
    )

    assert second_result.exit_code == 0
    assert "Existing environment to replace:" in second_result.stdout
    assert "VM 201" in second_result.stdout
    assert "Expected name: learnlab-full-course-201" in second_result.stdout
    assert "Current lesson: First Lesson" in second_result.stdout
    assert "Requested lesson: Second Lesson" in second_result.stdout
    replacement = store.active_environment("fake", "full-course")
    assert replacement is not None
    assert replacement.id != first_environment.id
    assert replacement.vmid == 202
    assert replacement.lesson_owner_id == "second"
    assert not first_known_hosts.exists()
    assert provider.operations.index("locate:201", 7) < provider.operations.index(
        "stop:201"
    )
    assert provider.operations.index("delete:201") < provider.operations.index(
        "allocate:202"
    )
    assert provider.operations == [
        "allocate:201",
        "clone:201:learnlab-full-course-201",
        "wait:clone-201",
        "locate:201",
        "start:201",
        "wait:start-201",
        "address:201",
        "locate:201",
        "stop:201",
        "wait:stop-201",
        "delete:201",
        "wait:delete-201",
        "locate:201",
        "allocate:202",
        "clone:202:learnlab-full-course-202",
        "wait:clone-202",
        "locate:202",
        "start:202",
        "wait:start-202",
        "address:202",
    ]
    assert SECRET not in first_result.stdout + second_result.stdout


def test_lesson_scope_cancellation_keeps_owned_vm_without_destructive_calls(
    monkeypatch: pytest.MonkeyPatch,
    isolated_xdg: Path,
) -> None:
    from learnlab import cli

    provider = FakeProvider((211, 212))
    ssh_runner = FakeSshRunner(provider.operations)
    install_public_cli_fakes(
        monkeypatch,
        two_lesson_course(EnvironmentScope.LESSON),
        provider,
        ssh_runner,
    )
    first_result = CliRunner().invoke(
        cli.app,
        ["start", COURSE_PATH],
        input="\n\ny\nq\n",
    )
    assert first_result.exit_code == 0
    store = StateStore(resolve_default_state_db(state_dir()))
    original = store.active_environment("fake", "full-course")
    assert original is not None
    operations_before_cancel = list(provider.operations)

    cancelled = CliRunner().invoke(
        cli.app,
        ["start", COURSE_PATH],
        input="2\nn\n",
    )

    assert cancelled.exit_code == 0
    assert "Progress saved." in cancelled.stdout
    assert provider.operations == operations_before_cancel
    assert not any(
        operation.startswith(("stop:", "delete:")) for operation in provider.operations
    )
    assert store.active_environment("fake", "full-course") == original
    assert store.completed_lessons("fake", "full-course") == {"first"}


def test_course_scope_ownership_mismatch_fails_before_provider_or_destroy_calls(
    monkeypatch: pytest.MonkeyPatch,
    isolated_xdg: Path,
) -> None:
    from learnlab import cli

    provider = FakeProvider((221,))
    ssh_runner = FakeSshRunner(provider.operations)
    install_public_cli_fakes(
        monkeypatch,
        two_lesson_course(EnvironmentScope.COURSE),
        provider,
        ssh_runner,
    )
    first_result = CliRunner().invoke(
        cli.app,
        ["start", COURSE_PATH],
        input="\n\ny\nq\n",
    )
    assert first_result.exit_code == 0
    store = StateStore(resolve_default_state_db(state_dir()))
    original = store.active_environment("fake", "full-course")
    assert original is not None
    operations_before_mismatch = list(provider.operations)
    provider.profile_fingerprint = "sha256:mismatched-provider"
    monkeypatch.setattr(
        cli,
        "provider_factory",
        lambda settings, profile_name, secret=None: provider,
    )

    mismatched = CliRunner().invoke(
        cli.app,
        ["resume", COURSE_PATH],
        input="\n",
    )

    assert mismatched.exit_code == 3
    assert "fingerprint does not match recorded ownership" in mismatched.stdout
    assert provider.operations == operations_before_mismatch
    assert not any(
        operation.startswith(("stop:", "delete:")) for operation in provider.operations
    )
    assert store.active_environment("fake", "full-course") == original


def test_none_scope_completes_without_loading_provider_configuration(
    monkeypatch: pytest.MonkeyPatch,
    isolated_xdg: Path,
) -> None:
    from learnlab import cli

    course = Course(
        collection_id="fake",
        id="full-course",
        title="Provider-Free Course",
        lessons=(simple_lesson("only", "Only Lesson"),),
        environment=EnvironmentPolicy(EnvironmentScope.NONE),
    )
    monkeypatch.setattr(cli, "catalog_factory", lambda: FakeCatalog(course))
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: pytest.fail("none scope must not load provider settings"),
    )
    monkeypatch.setattr(
        cli,
        "resolve_token_secret",
        lambda profile: pytest.fail("none scope must not resolve a secret"),
    )
    monkeypatch.setattr(
        cli,
        "provider_factory",
        lambda *args, **kwargs: pytest.fail("none scope must not build a provider"),
    )

    result = CliRunner().invoke(
        cli.app,
        ["start", COURSE_PATH, "--provider", "missing-profile"],
        input="\n\ny\nq\n",
    )

    assert result.exit_code == 0
    assert "Environment policy: none" in result.stdout
    assert "PASS (self-attested): Learner confirmed" in result.stdout
    store = StateStore(resolve_default_state_db(state_dir()))
    assert store.completed_lessons("fake", "full-course") == {"only"}
    assert store.list_environments() == []
    assert store.list_attempts() == []
    assert SECRET not in result.stdout
