from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from learnlab.state import (
    EnvironmentPhase,
    EnvironmentRecord,
    ProgressStatus,
    StateConflictError,
    StateStore,
)


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state_store = StateStore(tmp_path / "learnlab.db")
    state_store.initialize()
    return state_store


@pytest.fixture
def environment_fixture() -> Callable[..., EnvironmentRecord]:
    def build_environment(**overrides: object) -> EnvironmentRecord:
        values: dict[str, object] = {
            "id": "env-1",
            "collection_id": "proxmox",
            "course_id": "proxmox-admin",
            "lesson_id": "api-access",
            "attempt_id": None,
            "profile_name": "home-proxmox",
            "provider_type": "proxmox",
            "vmid": None,
            "node": None,
            "ip_address": None,
            "phase": EnvironmentPhase.ALLOCATING,
            "upid": None,
            "error_summary": None,
        }
        values.update(overrides)
        return EnvironmentRecord(**values)  # type: ignore[arg-type]

    return build_environment


def test_progress_persists_between_store_instances(tmp_path: Path) -> None:
    path = tmp_path / "learnlab.db"
    first = StateStore(path)
    first.initialize()
    first.mark_lesson(
        "proxmox", "proxmox-admin", "api-access", ProgressStatus.COMPLETED
    )

    second = StateStore(path)
    second.initialize()

    assert second.completed_lessons("proxmox", "proxmox-admin") == {"api-access"}


def test_only_one_active_environment_per_course(
    store: StateStore, environment_fixture: Callable[..., EnvironmentRecord]
) -> None:
    store.create_environment(environment_fixture(id="one"))

    with pytest.raises(StateConflictError, match="active environment"):
        store.create_environment(environment_fixture(id="two"))


def test_transition_records_each_remote_boundary(
    store: StateStore, environment_fixture: Callable[..., EnvironmentRecord]
) -> None:
    store.create_environment(environment_fixture(phase=EnvironmentPhase.ALLOCATING))

    store.transition_environment(
        "env-1", EnvironmentPhase.CLONING, vmid=102, upid="UPID:clone"
    )

    record = store.get_environment("env-1")
    assert record is not None
    assert (record.phase, record.vmid, record.upid) == (
        EnvironmentPhase.CLONING,
        102,
        "UPID:clone",
    )


def test_reset_course_refuses_active_environment(
    store: StateStore, environment_fixture: Callable[..., EnvironmentRecord]
) -> None:
    store.create_environment(environment_fixture())

    with pytest.raises(StateConflictError, match="destroy"):
        store.reset_scope("proxmox", "proxmox-admin")


def test_erase_all_can_preserve_only_completed_progress(store: StateStore) -> None:
    seed_completed_in_progress_and_attempts(store)

    store.erase_all(preserve_completed=True)

    assert store.completed_lessons("proxmox", "proxmox-admin") == {"api-access"}
    assert store.list_attempts() == []


def seed_completed_in_progress_and_attempts(store: StateStore) -> None:
    store.mark_lesson(
        "proxmox", "proxmox-admin", "api-access", ProgressStatus.COMPLETED
    )
    store.mark_lesson(
        "proxmox", "proxmox-admin", "api-tokens", ProgressStatus.IN_PROGRESS
    )
    store.create_attempt("proxmox", "proxmox-admin", "api-access")
