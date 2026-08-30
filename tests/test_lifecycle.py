from __future__ import annotations

import stat
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import RecordingProvider

from learnlab.config import ProxmoxProfile
from learnlab.curriculum import Course, Lesson, Step
from learnlab.errors import (
    ConfigurationError,
    ProviderCloneOutcomeUnknown,
    ProviderError,
    ProviderTaskFailed,
)
from learnlab.lifecycle import LifecycleError, LifecycleService, StartRequest
from learnlab.providers.base import VmLocation
from learnlab.ssh import create_known_hosts, render_ssh_command
from learnlab.state import (
    EnvironmentPhase,
    EnvironmentRecord,
    ProgressStatus,
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
                str,
                str,
                bool,
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
                record.provider_fingerprint,
                record.expected_vm_name,
                record.clone_uncertain,
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


class DestroyRecordingProvider(RecordingProvider):
    """Model VM presence and status while recording destroy boundaries."""

    def __init__(
        self,
        locations: dict[int, VmLocation],
        store: StateStore | None = None,
        *,
        fingerprint: str = "test-provider-fingerprint",
    ) -> None:
        super().__init__()
        self.profile_fingerprint = fingerprint
        self.locations = locations
        self.store = store
        self.failing_vmids: set[int] = set()
        self.delete_removes_vm = True
        self.observed_phases: dict[str, EnvironmentPhase] = {}

    def fail_for_vmid(self, vmid: int) -> None:
        self.failing_vmids.add(vmid)

    def locate_vm(self, vmid: int) -> VmLocation | None:
        self._record(f"locate:{vmid}")
        if vmid in self.failing_vmids:
            raise ProviderError(f"locate failed for {vmid}")
        return self.locations.get(vmid)

    def stop(self, vmid: int, node: str) -> str:
        self._observe_phase(f"stop:{vmid}")
        self._record(f"stop:{vmid}")
        current = self.locations[vmid]
        self.locations[vmid] = VmLocation(
            node=node,
            status="stopped",
            name=current.name,
        )
        return "stop"

    def delete(self, vmid: int, node: str) -> str:
        self._observe_phase(f"delete:{vmid}")
        self._record(f"delete:{vmid}")
        if self.delete_removes_vm:
            self.locations.pop(vmid, None)
        return "delete"

    def _observe_phase(self, operation: str) -> None:
        if self.store is None:
            return
        [record] = self.store.list_environments()
        self.observed_phases[operation] = record.phase


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
        (
            "allocate",
            EnvironmentPhase.ALLOCATING,
            None,
            None,
            None,
            None,
            "test-provider-fingerprint",
            "",
            False,
        ),
        (
            "clone",
            EnvironmentPhase.CLONING,
            102,
            None,
            None,
            None,
            "test-provider-fingerprint",
            "learnlab-proxmox-admin-102",
            True,
        ),
        (
            "wait:clone",
            EnvironmentPhase.CLONING,
            102,
            None,
            "clone",
            None,
            "test-provider-fingerprint",
            "learnlab-proxmox-admin-102",
            False,
        ),
        (
            "locate",
            EnvironmentPhase.CLONING,
            102,
            None,
            "clone",
            None,
            "test-provider-fingerprint",
            "learnlab-proxmox-admin-102",
            False,
        ),
        (
            "start",
            EnvironmentPhase.STOPPED,
            102,
            "pve02",
            "clone",
            None,
            "test-provider-fingerprint",
            "learnlab-proxmox-admin-102",
            False,
        ),
        (
            "wait:start",
            EnvironmentPhase.STARTING,
            102,
            "pve02",
            "start",
            None,
            "test-provider-fingerprint",
            "learnlab-proxmox-admin-102",
            False,
        ),
        (
            "wait_for_ipv4",
            EnvironmentPhase.RUNNING,
            102,
            "pve02",
            "start",
            None,
            "test-provider-fingerprint",
            "learnlab-proxmox-admin-102",
            False,
        ),
    ]


def test_destroy_refuses_repointed_provider_before_remote_mutation(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(store, environment_id="env-1", vmid=102, node="pve02")
    provider = DestroyRecordingProvider(
        {
            102: VmLocation(
                node="pve02",
                status="running",
                name="learnlab-proxmox-admin-102",
            )
        },
        fingerprint="different-provider-fingerprint",
    )

    summary = LifecycleService(store, provider, tmp_path).destroy_all(
        True, tuple(store.list_environments())
    )

    retained = store.get_environment("env-1")
    assert summary.failed == ["env-1"]
    assert provider.operations == []
    assert retained is not None
    assert retained.phase is EnvironmentPhase.FAILED
    assert "fingerprint" in (retained.error_summary or "")


def test_destroy_refuses_reused_vmid_with_unexpected_name(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(store, environment_id="env-1", vmid=102, node="pve02")
    provider = DestroyRecordingProvider(
        {102: VmLocation(node="pve02", status="running", name="unrelated-vm")}
    )

    summary = LifecycleService(store, provider, tmp_path).destroy_all(
        True, tuple(store.list_environments())
    )

    retained = store.get_environment("env-1")
    assert summary.failed == ["env-1"]
    assert provider.operations == ["locate:102"]
    assert retained is not None
    assert retained.phase is EnvironmentPhase.FAILED
    assert "name" in (retained.error_summary or "")


def test_destroy_retains_absent_vm_when_clone_outcome_is_uncertain(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(
        store,
        environment_id="env-1",
        vmid=102,
        node="pve02",
        phase=EnvironmentPhase.FAILED,
        clone_uncertain=True,
    )
    provider = DestroyRecordingProvider({})

    summary = LifecycleService(store, provider, tmp_path).destroy_all(
        True, tuple(store.list_environments())
    )

    retained = store.get_environment("env-1")
    assert summary.failed == ["env-1"]
    assert provider.operations == ["locate:102"]
    assert retained is not None
    assert retained.clone_uncertain is True
    assert "uncertain" in (retained.error_summary or "")


def test_later_destroy_reconciles_previously_absent_uncertain_clone(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(
        store,
        environment_id="env-1",
        vmid=102,
        node="pve02",
        phase=EnvironmentPhase.FAILED,
        clone_uncertain=True,
    )
    provider = DestroyRecordingProvider({})
    service = LifecycleService(store, provider, tmp_path)

    first = service.destroy_all(True, tuple(store.list_environments()))
    provider.locations[102] = VmLocation(
        node="pve02",
        status="stopped",
        name="learnlab-proxmox-admin-102",
    )
    second = service.destroy_all(True, tuple(store.list_environments()))

    assert first.failed == ["env-1"]
    assert second.destroyed == ["env-1"]
    assert store.list_environments() == []
    assert provider.operations == [
        "locate:102",
        "locate:102",
        "delete:102",
        "wait:delete",
        "locate:102",
    ]


def test_start_failure_retains_redacted_partial_environment(
    store: StateStore,
    failing_provider: RecordingProvider,
    profile_fixture: Callable[..., ProxmoxProfile],
    tmp_path: Path,
) -> None:
    failing_provider.fail_on("wait:clone", ProviderTaskFailed("secret-value"))

    with pytest.raises(LifecycleError, match="learnlab destroy") as caught:
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
    assert "secret-value" not in str(caught.value)
    assert "[REDACTED]" in str(caught.value)
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

    with pytest.raises(LifecycleError) as caught:
        LifecycleService(store, failing_provider, tmp_path).start(
            start_request(profile_fixture(node="pve02"))
        )

    [record] = store.list_environments()
    assert record.error_summary is not None
    assert len(record.error_summary) <= 500
    assert len(str(caught.value)) < 700


def test_lost_clone_response_persists_uncertainty_and_expected_name(
    store: StateStore,
    failing_provider: RecordingProvider,
    profile_fixture: Callable[..., ProxmoxProfile],
    tmp_path: Path,
) -> None:
    failing_provider.fail_on(
        "clone:102",
        ProviderCloneOutcomeUnknown("clone response lost with secret-value"),
    )

    with pytest.raises(LifecycleError) as caught:
        LifecycleService(
            store,
            failing_provider,
            tmp_path,
            secrets={"secret-value"},
        ).start(start_request(profile_fixture(node="pve02")))

    [record] = store.list_environments()
    assert record.phase is EnvironmentPhase.FAILED
    assert record.expected_vm_name == "learnlab-proxmox-admin-102"
    assert record.clone_uncertain is True
    assert "[REDACTED]" in str(caught.value)
    assert "secret-value" not in str(caught.value)
    assert failing_provider.operations == ["allocate_vmid", "clone:102"]


def test_definitive_clone_rejection_does_not_mark_outcome_uncertain(
    store: StateStore,
    failing_provider: RecordingProvider,
    profile_fixture: Callable[..., ProxmoxProfile],
    tmp_path: Path,
) -> None:
    failing_provider.fail_on("clone:102", ProviderError("clone rejected"))

    with pytest.raises(LifecycleError, match="clone rejected"):
        LifecycleService(store, failing_provider, tmp_path).start(
            start_request(profile_fixture(node="pve02"))
        )

    [record] = store.list_environments()
    assert record.phase is EnvironmentPhase.FAILED
    assert record.clone_uncertain is False


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


def test_destroy_stops_running_vm_then_deletes_and_clears_record(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(
        store,
        environment_id="env-1",
        vmid=102,
        node="pve02",
        phase=EnvironmentPhase.RUNNING,
    )
    provider = DestroyRecordingProvider(
        {
            102: VmLocation(
                node="pve02",
                status="running",
                name="learnlab-proxmox-admin-102",
            )
        }
    )

    summary = LifecycleService(store, provider, tmp_path).destroy_all(
        True, tuple(store.list_environments())
    )

    assert provider.operations == [
        "locate:102",
        "stop:102",
        "wait:stop",
        "delete:102",
        "wait:delete",
        "locate:102",
    ]
    assert summary.destroyed == ["env-1"]
    assert store.list_environments() == []


def test_destroy_absent_vm_clears_local_environment_without_delete(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(
        store,
        environment_id="env-1",
        vmid=102,
        node="pve02",
        phase=EnvironmentPhase.FAILED,
    )
    environment_dir = tmp_path / "environments" / "env-1"
    environment_dir.mkdir(parents=True)
    (environment_dir / "known_hosts").write_text("host key\n")
    provider = DestroyRecordingProvider({})

    summary = LifecycleService(store, provider, tmp_path).destroy_all(
        True, tuple(store.list_environments())
    )

    assert provider.operations == ["locate:102"]
    assert summary.destroyed == ["env-1"]
    assert store.list_environments() == []
    assert not environment_dir.exists()


def test_destroy_failure_retains_record_and_continues(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(store, environment_id="env-102", vmid=102, node="pve02")
    seed_environment(
        store,
        environment_id="env-103",
        course_id="linux-basics",
        vmid=103,
        node="pve03",
    )
    provider = DestroyRecordingProvider(
        {
            102: VmLocation(
                node="pve02",
                status="stopped",
                name="learnlab-proxmox-admin-102",
            ),
            103: VmLocation(
                node="pve03",
                status="stopped",
                name="learnlab-linux-basics-103",
            ),
        }
    )
    provider.fail_for_vmid(102)

    summary = LifecycleService(store, provider, tmp_path).destroy_all(
        True, tuple(store.list_environments())
    )

    assert summary.failed == ["env-102"]
    assert summary.destroyed == ["env-103"]
    assert store.get_environment("env-102") is not None
    assert store.get_environment("env-103") is None
    assert provider.operations == [
        "locate:102",
        "locate:103",
        "delete:103",
        "wait:delete",
        "locate:103",
    ]


def test_destroy_rejects_empty_environment_id_without_removing_shared_directory(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(store, environment_id="", vmid=102, node="pve02")
    environments_dir = tmp_path / "environments"
    environments_dir.mkdir()
    sentinel = environments_dir / "keep-me"
    sentinel.write_text("retained\n")
    provider = DestroyRecordingProvider({})

    summary = LifecycleService(store, provider, tmp_path).destroy_all(
        True, tuple(store.list_environments())
    )

    assert summary.failed == [""]
    assert sentinel.read_text() == "retained\n"
    assert store.get_environment("") is not None


@pytest.mark.parametrize(
    ("status", "failing_operation", "expected_phase"),
    [
        ("running", "stop:102", EnvironmentPhase.STOPPING),
        ("stopped", "delete:102", EnvironmentPhase.DELETING),
    ],
)
def test_destroy_persists_destructive_phase_before_provider_mutation(
    store: StateStore,
    tmp_path: Path,
    status: str,
    failing_operation: str,
    expected_phase: EnvironmentPhase,
) -> None:
    seed_environment(store, environment_id="env-1", vmid=102, node="pve02")
    provider = DestroyRecordingProvider(
        {
            102: VmLocation(
                node="pve02",
                status=status,
                name="learnlab-proxmox-admin-102",
            )
        },
        store,
    )
    provider.fail_on(failing_operation, ProviderError("provider refused"))

    summary = LifecycleService(store, provider, tmp_path).destroy_all(
        True, tuple(store.list_environments())
    )

    retained = store.get_environment("env-1")
    assert summary.failed == ["env-1"]
    assert provider.observed_phases[failing_operation] is expected_phase
    assert retained is not None
    assert retained.phase is EnvironmentPhase.FAILED
    assert retained.error_summary == "provider refused"


def test_destroy_retains_record_when_vm_remains_after_delete(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(store, environment_id="env-1", vmid=102, node="pve02")
    provider = DestroyRecordingProvider(
        {
            102: VmLocation(
                node="pve02",
                status="stopped",
                name="learnlab-proxmox-admin-102",
            )
        }
    )
    provider.delete_removes_vm = False

    summary = LifecycleService(store, provider, tmp_path).destroy_all(
        True, tuple(store.list_environments())
    )

    assert summary.failed == ["env-1"]
    assert store.get_environment("env-1") is not None
    assert provider.operations[-1] == "locate:102"


def test_destroy_partial_failure_leaves_all_progress_and_attempts_untouched(
    store: StateStore, tmp_path: Path
) -> None:
    store.complete_lesson("proxmox", "proxmox-admin", "api-access")
    store.start_lesson("proxmox", "proxmox-admin", "api-tokens")
    store.create_attempt("proxmox", "proxmox-admin", "api-access")
    seed_environment(store, environment_id="env-1", vmid=102, node="pve02")
    provider = DestroyRecordingProvider(
        {
            102: VmLocation(
                node="pve02",
                status="stopped",
                name="learnlab-proxmox-admin-102",
            )
        }
    )
    provider.fail_for_vmid(102)

    LifecycleService(store, provider, tmp_path).destroy_all(
        True, tuple(store.list_environments())
    )

    assert store.lesson_statuses("proxmox", "proxmox-admin") == {
        "api-access": ProgressStatus.COMPLETED,
        "api-tokens": ProgressStatus.IN_PROGRESS,
    }
    assert len(store.list_attempts()) == 1


def test_destroy_success_preserves_only_completed_progress(
    store: StateStore, tmp_path: Path
) -> None:
    store.complete_lesson("proxmox", "proxmox-admin", "api-access")
    store.start_lesson("proxmox", "proxmox-admin", "api-tokens")
    store.create_attempt("proxmox", "proxmox-admin", "api-access")
    seed_environment(store, environment_id="env-1", vmid=102, node="pve02")

    LifecycleService(store, DestroyRecordingProvider({}), tmp_path).destroy_all(
        True, tuple(store.list_environments())
    )

    assert store.lesson_statuses("proxmox", "proxmox-admin") == {
        "api-access": ProgressStatus.COMPLETED,
    }
    assert store.list_attempts() == []


def test_destroy_routes_each_environment_to_its_recorded_provider_profile(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(
        store,
        environment_id="env-home",
        profile_name="home-proxmox",
        vmid=102,
        node="home-node",
    )
    seed_environment(
        store,
        environment_id="env-lab",
        profile_name="lab-proxmox",
        course_id="linux-basics",
        vmid=102,
        node="lab-node",
    )
    home_provider = DestroyRecordingProvider(
        {
            102: VmLocation(
                node="home-node",
                status="stopped",
                name="learnlab-proxmox-admin-102",
            )
        }
    )
    lab_provider = DestroyRecordingProvider(
        {
            102: VmLocation(
                node="lab-node",
                status="stopped",
                name="learnlab-linux-basics-102",
            )
        }
    )

    summary = LifecycleService(
        store,
        {
            "home-proxmox": home_provider,
            "lab-proxmox": lab_provider,
        },
        tmp_path,
    ).destroy_all(True, tuple(store.list_environments()))

    assert summary.destroyed == ["env-home", "env-lab"]
    assert home_provider.operations == [
        "locate:102",
        "delete:102",
        "wait:delete",
        "locate:102",
    ]
    assert lab_provider.operations == [
        "locate:102",
        "delete:102",
        "wait:delete",
        "locate:102",
    ]


def test_destroy_touches_only_the_immutable_confirmed_snapshot(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(store, environment_id="env-confirmed", vmid=102, node="pve02")
    confirmed = tuple(store.list_environments())
    seed_environment(
        store,
        environment_id="env-later",
        course_id="linux-basics",
        vmid=103,
        node="pve03",
    )
    provider = DestroyRecordingProvider(
        {
            102: VmLocation(
                node="pve02",
                status="stopped",
                name="learnlab-proxmox-admin-102",
            ),
            103: VmLocation(
                node="pve03",
                status="stopped",
                name="learnlab-linux-basics-103",
            ),
        }
    )

    summary = LifecycleService(store, provider, tmp_path).destroy_all(True, confirmed)

    assert summary.destroyed == ["env-confirmed"]
    assert summary.failed == []
    assert provider.operations == [
        "locate:102",
        "delete:102",
        "wait:delete",
        "locate:102",
    ]
    assert store.get_environment("env-confirmed") is None
    assert store.get_environment("env-later") is not None


def test_destroy_provider_resolution_failure_retains_target_and_continues(
    store: StateStore, tmp_path: Path
) -> None:
    seed_environment(
        store,
        environment_id="env-invalid",
        profile_name="missing-secret",
        vmid=102,
        node="pve02",
    )
    seed_environment(
        store,
        environment_id="env-valid",
        profile_name="home-proxmox",
        course_id="linux-basics",
        vmid=103,
        node="pve03",
    )
    confirmed = tuple(store.list_environments())
    valid_provider = DestroyRecordingProvider(
        {
            103: VmLocation(
                node="pve03",
                status="stopped",
                name="learnlab-linux-basics-103",
            )
        }
    )

    summary = LifecycleService(
        store,
        {
            "missing-secret": ConfigurationError("secret-value is unavailable"),
            "home-proxmox": valid_provider,
        },
        tmp_path,
        secrets={"secret-value"},
    ).destroy_all(True, confirmed)

    retained = store.get_environment("env-invalid")
    assert summary.failed == ["env-invalid"]
    assert summary.destroyed == ["env-valid"]
    assert retained is not None
    assert retained.phase is EnvironmentPhase.FAILED
    assert retained.error_summary == "[REDACTED] is unavailable"
    assert store.get_environment("env-valid") is None


def seed_environment(
    store: StateStore,
    *,
    environment_id: str,
    vmid: int,
    node: str,
    course_id: str = "proxmox-admin",
    profile_name: str = "home-proxmox",
    phase: EnvironmentPhase = EnvironmentPhase.STOPPED,
    provider_endpoint: str = "https://proxmox.example.test:8006",
    provider_fingerprint: str = "test-provider-fingerprint",
    expected_vm_name: str | None = None,
    clone_uncertain: bool = False,
) -> None:
    store.create_environment(
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
            provider_endpoint=provider_endpoint,
            provider_fingerprint=provider_fingerprint,
            expected_vm_name=(expected_vm_name or f"learnlab-{course_id}-{vmid}"),
            clone_uncertain=clone_uncertain,
        )
    )
