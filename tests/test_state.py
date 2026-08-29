from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

import learnlab.state as state_module
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


@pytest.mark.parametrize(
    ("operation", "interleaved_statement"),
    [
        ("reset", "DELETE FROM progress"),
        ("erase", "DELETE FROM attempts"),
    ],
)
def test_scope_clear_blocks_an_interleaved_environment_create(
    tmp_path: Path, operation: str, interleaved_statement: str
) -> None:
    store = InterleavingStateStore(tmp_path / "learnlab.db")
    store.initialize()
    store.mark_lesson(
        "proxmox", "proxmox-admin", "api-access", ProgressStatus.COMPLETED
    )
    store.arm_interleaved_create(interleaved_statement)

    if operation == "reset":
        store.reset_scope("proxmox", "proxmox-admin")
    else:
        store.erase_all(preserve_completed=False)

    assert store.interleaved_create_was_blocked is True
    assert store.interleaved_create_succeeded is False
    assert store.active_environment("proxmox", "proxmox-admin") is None


def test_initialize_rolls_back_all_schema_objects_after_later_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "learnlab.db"
    monkeypatch.setattr(
        state_module,
        "_SCHEMA",
        f"{state_module._SCHEMA}\nCREATE TABLE broken (",
    )

    with pytest.raises(sqlite3.OperationalError):
        StateStore(path).initialize()

    connection = sqlite3.connect(path)
    try:
        objects = connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
        ).fetchall()
    finally:
        connection.close()
    assert objects == []


def test_environment_creation_generates_utc_timestamps_internally(
    store: StateStore, environment_fixture: Callable[..., EnvironmentRecord]
) -> None:
    record = store.create_environment(
        environment_fixture(
            created_at="not-a-timestamp",
            updated_at="2000-01-01T00:00:00+05:00",
        )
    )
    persisted = store.get_environment(record.id)

    assert persisted is not None
    assert persisted.created_at == persisted.updated_at
    assert persisted.created_at not in {
        "not-a-timestamp",
        "2000-01-01T00:00:00+05:00",
    }
    assert persisted.created_at is not None
    assert datetime.fromisoformat(persisted.created_at.replace("Z", "+00:00")).tzinfo is UTC


class InterleavingStateStore(StateStore):
    """Runs a real second connection at a selected statement boundary."""

    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path)
        self._statement_to_interleave: str | None = None
        self.interleaved_create_succeeded = False
        self.interleaved_create_was_blocked = False

    def arm_interleaved_create(self, statement: str) -> None:
        self._statement_to_interleave = statement

    def _connect(self) -> sqlite3.Connection:
        connection = super()._connect()

        def interleave(statement: str) -> None:
            if self._statement_to_interleave is None or not statement.startswith(
                self._statement_to_interleave
            ):
                return
            self._statement_to_interleave = None
            other = sqlite3.connect(self.db_path, timeout=0)
            try:
                other.execute(
                    """
                    INSERT INTO environments (
                        id, collection_id, course_id, lesson_id, attempt_id,
                        profile_name, provider_type, phase, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "interleaved",
                        "proxmox",
                        "proxmox-admin",
                        "api-access",
                        None,
                        "home-proxmox",
                        "proxmox",
                        EnvironmentPhase.ALLOCATING.value,
                        "2026-08-29T00:00:00Z",
                        "2026-08-29T00:00:00Z",
                    ),
                )
                other.commit()
                self.interleaved_create_succeeded = True
            except sqlite3.OperationalError as error:
                assert "locked" in str(error)
                self.interleaved_create_was_blocked = True
            finally:
                other.close()

        connection.set_trace_callback(interleave)
        return connection
