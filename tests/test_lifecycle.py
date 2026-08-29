from __future__ import annotations

import stat
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import RecordingProvider

from learnlab.config import ProxmoxProfile
from learnlab.curriculum import Course, Lesson, Step
from learnlab.errors import ProviderTaskFailed
from learnlab.lifecycle import LifecycleError, LifecycleService, StartRequest
from learnlab.providers.base import VmLocation
from learnlab.ssh import create_known_hosts, render_ssh_command
from learnlab.state import (
    EnvironmentPhase,
    StateConflictError,
    StateStore,
)


class StateObservingProvider(RecordingProvider):
    """Record real persisted state immediately before each remote boundary."""

    def __init__(self, store: StateStore) -> None:
        super().__init__()
        self._store = store
        self.snapshots: list[
            tuple[
                str,
                EnvironmentPhase,
                int | None,
                str | None,
                str | None,
                str | None,
            ]
        ] = []

    def _snapshot(self, operation: str) -> None:
        [record] = self._store.list_environments()
        self.snapshots.append(
            (
                operation,
                record.phase,
                record.vmid,
                record.node,
                record.upid,
                record.ip_address,
            )
        )

    def allocate_vmid(self) -> int:
        self._snapshot("allocate")
        return super().allocate_vmid()

    def clone(self, vmid: int, name: str) -> str:
        self._snapshot("clone")
        return super().clone(vmid, name)

    def wait_for_task(self, node: str, upid: str, timeout: float) -> None:
        self._snapshot(f"wait:{upid}")
        super().wait_for_task(node, upid, timeout)

    def locate_vm(self, vmid: int) -> VmLocation | None:
        self._snapshot("locate")
        return super().locate_vm(vmid)

    def start(self, vmid: int, node: str) -> str:
        self._snapshot("start")
        return super().start(vmid, node)

    def wait_for_ipv4(self, vmid: int, node: str, timeout: float) -> str:
        self._snapshot("wait_for_ipv4")
        return super().wait_for_ipv4(vmid, node, timeout)


def start_request(profile: ProxmoxProfile) -> StartRequest:
    lesson = Lesson(
        id="api-access",
        title="API Access",
        steps=(Step(id="configure", title="Configure", content="Configure it."),),
    )
    course = Course(
        collection_id="proxmox",
        id="proxmox-admin",
        title="Proxmox Administration",
        lessons=(lesson,),
    )
    return StartRequest(
        course=course,
        lesson=lesson,
        profile=profile,
        provider_type="proxmox",
    )


def test_start_persists_remote_boundaries_in_order(
    store: StateStore,
    recording_provider: RecordingProvider,
    profile_fixture: Callable[..., ProxmoxProfile],
    tmp_path: Path,
) -> None:
    service = LifecycleService(store, recording_provider, tmp_path)

    started = service.start(start_request(profile_fixture(node="pve02")))

    assert recording_provider.operations == [
        "allocate_vmid",
        "clone:102",
        "wait:clone",
        "locate:102",
        "start:102",
        "wait:start",
        "wait_for_ipv4:102",
    ]
    assert started.ip_address == "192.0.2.10"
    assert started.known_hosts.exists()
    record = store.get_environment(started.environment_id)
    assert record is not None
    assert record.phase is EnvironmentPhase.RUNNING
    assert record.vmid == 102


def test_start_persists_state_before_each_next_remote_boundary(
    store: StateStore,
    profile_fixture: Callable[..., ProxmoxProfile],
    tmp_path: Path,
) -> None:
    provider = StateObservingProvider(store)

    LifecycleService(store, provider, tmp_path).start(
        start_request(profile_fixture(node="pve02"))
    )

    assert provider.snapshots == [
        ("allocate", EnvironmentPhase.ALLOCATING, None, None, None, None),
        ("clone", EnvironmentPhase.ALLOCATING, 102, None, None, None),
        ("wait:clone", EnvironmentPhase.CLONING, 102, None, "clone", None),
        ("locate", EnvironmentPhase.CLONING, 102, None, "clone", None),
        ("start", EnvironmentPhase.STOPPED, 102, "pve02", "clone", None),
        ("wait:start", EnvironmentPhase.STARTING, 102, "pve02", "start", None),
        ("wait_for_ipv4", EnvironmentPhase.RUNNING, 102, "pve02", "start", None),
    ]


def test_start_failure_retains_redacted_partial_environment(
    store: StateStore,
    failing_provider: RecordingProvider,
    profile_fixture: Callable[..., ProxmoxProfile],
    tmp_path: Path,
) -> None:
    failing_provider.fail_on("wait:clone", ProviderTaskFailed("secret-value"))

    with pytest.raises(LifecycleError, match="learnlab destroy"):
        LifecycleService(
            store,
            failing_provider,
            tmp_path,
            secrets={"secret-value"},
        ).start(start_request(profile_fixture(node="pve02")))

    [record] = store.list_environments()
    assert record.phase is EnvironmentPhase.FAILED
    assert record.error_summary is not None
    assert "secret-value" not in record.error_summary
    assert not any(
        operation.startswith(("stop:", "delete:"))
        for operation in failing_provider.operations
    )


def test_start_failure_bounds_retained_error_summary(
    store: StateStore,
    failing_provider: RecordingProvider,
    profile_fixture: Callable[..., ProxmoxProfile],
    tmp_path: Path,
) -> None:
    failing_provider.fail_on("wait:clone", ProviderTaskFailed("x" * 1_000))

    with pytest.raises(LifecycleError):
        LifecycleService(store, failing_provider, tmp_path).start(
            start_request(profile_fixture(node="pve02"))
        )

    [record] = store.list_environments()
    assert record.error_summary is not None
    assert len(record.error_summary) <= 500


def test_start_refuses_second_environment_for_course(
    store: StateStore,
    recording_provider: RecordingProvider,
    profile_fixture: Callable[..., ProxmoxProfile],
    tmp_path: Path,
) -> None:
    service = LifecycleService(store, recording_provider, tmp_path)
    request = start_request(profile_fixture(node="pve02"))
    service.start(request)

    with pytest.raises(StateConflictError, match="already has an environment"):
        service.start(request)

    assert recording_provider.operations.count("allocate_vmid") == 1


def test_create_known_hosts_uses_private_environment_permissions(
    tmp_path: Path,
) -> None:
    known_hosts = create_known_hosts(tmp_path, "env-1")

    assert known_hosts == tmp_path / "environments" / "env-1" / "known_hosts"
    assert known_hosts.read_text() == ""
    assert stat.S_IMODE(known_hosts.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(known_hosts.stat().st_mode) == 0o600


def test_create_known_hosts_does_not_touch_normal_ssh_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    normal_known_hosts = tmp_path / "home" / ".ssh" / "known_hosts"
    normal_known_hosts.parent.mkdir(parents=True)
    normal_known_hosts.write_text("trusted-host-key\n")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    create_known_hosts(tmp_path / "state", "env-1")

    assert normal_known_hosts.read_text() == "trusted-host-key\n"


def test_render_ssh_command_shell_quotes_isolated_paths(
    profile_fixture: Callable[..., ProxmoxProfile],
) -> None:
    profile = profile_fixture(
        ssh_identity_file=Path("/keys/student key"),
        ssh_user="student",
    )

    command = render_ssh_command(
        profile,
        "192.0.2.10",
        Path("/state env/known_hosts"),
    )

    assert command == (
        "ssh -i '/keys/student key' -o "
        "'UserKnownHostsFile=/state env/known_hosts' student@192.0.2.10"
    )


def test_start_normalizes_and_bounds_vm_name(
    store: StateStore,
    recording_provider: RecordingProvider,
    profile_fixture: Callable[..., ProxmoxProfile],
    tmp_path: Path,
) -> None:
    request = start_request(profile_fixture(node="pve02"))
    request = replace(
        request,
        course=replace(request.course, id=f"Admin Course___{'X' * 80}"),
    )

    LifecycleService(store, recording_provider, tmp_path).start(request)

    assert recording_provider.clone_names == [
        "learnlab-admin-course-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-102"
    ]
