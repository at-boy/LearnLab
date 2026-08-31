from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

import learnlab.state as state_module
from learnlab.curriculum import MAX_EVIDENCE_BYTES, VerificationType
from learnlab.state import (
    CompletionSource,
    EnvironmentPhase,
    EnvironmentRecord,
    ProgressStatus,
    SessionCursor,
    StateConflictError,
    StateStore,
    StepStatus,
    VerificationStatus,
)

COURSE_PATH = ("proxmox", "proxmox-admin")
LESSON_PATH = (*COURSE_PATH, "api-access")
STEP_PATH = (*LESSON_PATH, "inspect")


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
    assert (
        datetime.fromisoformat(persisted.created_at.replace("Z", "+00:00")).tzinfo
        is UTC
    )


def test_initialize_migrates_pre_ownership_environment_schema(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
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
            INSERT INTO environments VALUES (
                'legacy-env', 'proxmox', 'proxmox-admin', 'api-access', NULL,
                'home-proxmox', 'proxmox', 102, 'pve02', NULL, 'failed', NULL,
                NULL, '2026-08-29T00:00:00Z', '2026-08-29T00:00:00Z'
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    store = StateStore(path)
    store.initialize()

    record = store.get_environment("legacy-env")
    assert record is not None
    assert record.provider_endpoint == ""
    assert record.provider_fingerprint == ""
    assert record.expected_vm_name == ""
    assert record.clone_uncertain is False


def test_session_migration_is_additive_and_marks_legacy_completion(
    tmp_path: Path,
) -> None:
    path = tmp_path / "current.db"
    connection = sqlite3.connect(path)
    try:
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
                attempt_id TEXT REFERENCES attempts(id) ON DELETE RESTRICT,
                profile_name TEXT NOT NULL,
                provider_type TEXT NOT NULL,
                vmid INTEGER,
                node TEXT,
                ip_address TEXT,
                phase TEXT NOT NULL,
                upid TEXT,
                error_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                provider_endpoint TEXT NOT NULL DEFAULT '',
                provider_fingerprint TEXT NOT NULL DEFAULT '',
                expected_vm_name TEXT NOT NULL DEFAULT '',
                clone_uncertain INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO progress VALUES
                ('proxmox', 'proxmox-admin', 'api-access', 'completed',
                 '2026-08-29T00:00:00Z', '2026-08-29T01:00:00Z'),
                ('proxmox', 'proxmox-admin', 'api-tokens', 'in_progress',
                 '2026-08-29T02:00:00Z', '2026-08-29T03:00:00Z');
            INSERT INTO attempts VALUES
                ('attempt-1', 'proxmox', 'proxmox-admin', 'api-access',
                 '2026-08-29T00:00:00Z');
            INSERT INTO environments VALUES (
                'legacy-env', 'proxmox', 'proxmox-admin', 'api-access',
                'attempt-1', 'home-proxmox', 'proxmox', 102, 'pve02',
                '192.0.2.10', 'running', 'UPID:start', NULL,
                '2026-08-29T00:00:00Z', '2026-08-29T01:00:00Z',
                'https://proxmox.example.test:8006', 'sha256:owned',
                'learnlab-proxmox-admin-102', 0
            );
            """
        )
        before = {
            "progress": connection.execute("SELECT * FROM progress").fetchall(),
            "attempts": connection.execute("SELECT * FROM attempts").fetchall(),
            "environments": connection.execute("SELECT * FROM environments").fetchall(),
        }
        connection.commit()
    finally:
        connection.close()

    store = StateStore(path)
    store.initialize()

    connection = sqlite3.connect(path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"session_cursors", "step_progress", "verification_progress"} <= tables
        assert "completion_source" in {
            row[1] for row in connection.execute("PRAGMA table_info(progress)")
        }
        original_columns = {
            "progress": 6,
            "attempts": 5,
            "environments": 19,
        }
        after = {
            "progress": [
                row[: original_columns["progress"]]
                for row in connection.execute("SELECT * FROM progress").fetchall()
            ],
            "attempts": [
                row[: original_columns["attempts"]]
                for row in connection.execute("SELECT * FROM attempts").fetchall()
            ],
            "environments": [
                row[: original_columns["environments"]]
                for row in connection.execute("SELECT * FROM environments").fetchall()
            ],
        }
        assert after == before
        assert connection.execute(
            "SELECT COUNT(*) FROM verification_progress"
        ).fetchone() == (0,)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE progress SET completion_source = 'invented' "
                "WHERE lesson_id = 'api-access'"
            )
    finally:
        connection.close()

    assert (
        store.lesson_completion_source(LESSON_PATH)
        is state_module.CompletionSource.LEGACY
    )


def test_failed_verification_increments_attempt_without_completing_step(
    store: StateStore,
) -> None:
    store.start_step(STEP_PATH)
    store.record_verification_result(
        STEP_PATH,
        "check-os",
        passed=False,
        evidence="bad",
        validator_type=VerificationType.REMOTE_COMMAND,
    )

    [record] = store.verification_records(STEP_PATH)
    assert record.status is VerificationStatus.FAILED
    assert record.attempt_count == 1
    assert store.step_statuses(LESSON_PATH)["inspect"] is StepStatus.IN_PROGRESS


def test_retry_preserves_prior_passed_verifications(store: StateStore) -> None:
    store.start_step(STEP_PATH)
    store.record_verification_result(
        STEP_PATH,
        "check-os",
        passed=True,
        evidence="NixOS",
        validator_type=VerificationType.TEXT_EVIDENCE,
    )
    store.record_verification_result(
        STEP_PATH,
        "check-agent",
        passed=False,
        evidence="not ready",
        validator_type=VerificationType.PROVIDER_CHECK,
    )
    store.record_verification_result(
        STEP_PATH,
        "check-agent",
        passed=True,
        evidence="ready",
        validator_type=VerificationType.PROVIDER_CHECK,
    )

    records = {
        record.verification_id: record
        for record in store.verification_records(STEP_PATH)
    }
    assert records["check-os"].status is VerificationStatus.PASSED
    assert records["check-os"].attempt_count == 1
    assert records["check-agent"].status is VerificationStatus.PASSED
    assert records["check-agent"].attempt_count == 2


def test_failed_retry_does_not_clear_a_prior_pass(store: StateStore) -> None:
    store.start_step(STEP_PATH)
    store.record_verification_result(
        STEP_PATH,
        "check-os",
        passed=True,
        evidence="original pass",
        validator_type=VerificationType.REMOTE_COMMAND,
    )

    store.record_verification_result(
        STEP_PATH,
        "check-os",
        passed=False,
        evidence="later failure",
        validator_type=VerificationType.REMOTE_COMMAND,
    )

    [record] = store.verification_records(STEP_PATH)
    assert record.status is VerificationStatus.PASSED
    assert record.evidence == "original pass"
    assert record.attempt_count == 2


def test_all_verifications_complete_step_and_lesson_transactionally(
    store: StateStore,
) -> None:
    _seed_two_passed_verifications(store)

    store.complete_step(STEP_PATH, ("check-os", "check-agent"))

    assert store.step_statuses(LESSON_PATH)["inspect"] is StepStatus.COMPLETED
    store.complete_lesson_validated(LESSON_PATH, ("inspect",))
    assert store.lesson_completion_source(LESSON_PATH) is CompletionSource.VALIDATED


def test_step_completion_rejects_missing_expected_verification(
    store: StateStore,
) -> None:
    store.start_step(STEP_PATH)
    store.record_verification_result(
        STEP_PATH,
        "check-os",
        passed=True,
        evidence="ok",
        validator_type=VerificationType.REMOTE_COMMAND,
    )

    with pytest.raises(StateConflictError, match="check-agent"):
        store.complete_step(STEP_PATH, ("check-os", "check-agent"))

    assert store.step_statuses(LESSON_PATH)["inspect"] is StepStatus.IN_PROGRESS


def test_validated_lesson_completion_rejects_missing_expected_step(
    store: StateStore,
) -> None:
    _seed_two_passed_verifications(store)
    store.complete_step(STEP_PATH, ("check-os", "check-agent"))

    with pytest.raises(StateConflictError, match="configure"):
        store.complete_lesson_validated(LESSON_PATH, ("inspect", "configure"))

    assert store.lesson_completion_source(LESSON_PATH) is None


def test_session_cursor_persists_between_store_instances(tmp_path: Path) -> None:
    path = tmp_path / "learnlab.db"
    first = StateStore(path)
    first.initialize()

    stored = first.set_session_cursor(
        COURSE_PATH,
        lesson_id="api-access",
        step_id="inspect",
        verification_id="check-os",
    )
    second = StateStore(path)
    second.initialize()

    assert second.session_cursor(COURSE_PATH) == stored
    assert stored == SessionCursor(
        collection_id="proxmox",
        course_id="proxmox-admin",
        lesson_id="api-access",
        step_id="inspect",
        verification_id="check-os",
        updated_at=stored.updated_at,
    )


def test_manual_verification_is_persisted_as_self_attested(store: StateStore) -> None:
    store.start_step(STEP_PATH)
    store.record_verification_result(
        STEP_PATH,
        "reviewed-output",
        passed=True,
        evidence="confirmed",
        validator_type=VerificationType.MANUAL_CONFIRMATION,
        self_attested=True,
    )

    [record] = store.verification_records(STEP_PATH)
    assert record.self_attested is True
    assert record.validator_type is VerificationType.MANUAL_CONFIRMATION


def test_oversized_evidence_is_rejected_before_database_access(
    tmp_path: Path,
) -> None:
    store = DatabaseAccessForbiddenStore(tmp_path / "unused.db")

    with pytest.raises(ValueError, match="8192 bytes"):
        store.record_verification_result(
            STEP_PATH,
            "check-os",
            passed=False,
            evidence="x" * (MAX_EVIDENCE_BYTES + 1),
            validator_type=VerificationType.TEXT_EVIDENCE,
        )


def test_reset_deletes_session_step_and_verification_state(store: StateStore) -> None:
    store.set_session_cursor(COURSE_PATH, "api-access", "inspect", "check-os")
    _seed_two_passed_verifications(store)
    store.reset_scope(*COURSE_PATH)

    assert store.session_cursor(COURSE_PATH) is None
    assert store.step_statuses(LESSON_PATH) == {}
    assert store.verification_records(STEP_PATH) == []


def test_erase_preserve_progress_retains_completed_steps_and_passed_checks(
    store: StateStore,
) -> None:
    _seed_two_passed_verifications(store)
    store.complete_step(STEP_PATH, ("check-os", "check-agent"))
    incomplete_path = (*LESSON_PATH, "configure")
    store.start_step(incomplete_path)
    store.record_verification_result(
        incomplete_path,
        "passed-config",
        passed=True,
        evidence="good",
        validator_type=VerificationType.REMOTE_COMMAND,
    )
    store.record_verification_result(
        incomplete_path,
        "failed-config",
        passed=False,
        evidence="bad",
        validator_type=VerificationType.REMOTE_COMMAND,
    )
    store.set_session_cursor(COURSE_PATH, "api-access", "configure", "failed-config")

    store.erase_all(preserve_completed=True)

    assert store.session_cursor(COURSE_PATH) is None
    assert store.step_statuses(LESSON_PATH) == {"inspect": StepStatus.COMPLETED}
    assert {
        record.verification_id for record in store.verification_records(STEP_PATH)
    } == {"check-os", "check-agent"}
    [preserved] = store.verification_records(incomplete_path)
    assert preserved.verification_id == "passed-config"
    assert preserved.status is VerificationStatus.PASSED


def test_erase_without_preservation_removes_all_session_progress(
    store: StateStore,
) -> None:
    _seed_two_passed_verifications(store)
    store.complete_step(STEP_PATH, ("check-os", "check-agent"))
    store.set_session_cursor(COURSE_PATH, "api-access", "inspect", "check-os")

    store.erase_all(preserve_completed=False)

    assert store.session_cursor(COURSE_PATH) is None
    assert store.step_statuses(LESSON_PATH) == {}
    assert store.verification_records(STEP_PATH) == []


def test_manual_lesson_completion_records_override_provenance(
    store: StateStore,
) -> None:
    store.complete_lesson(*LESSON_PATH, source=CompletionSource.MANUAL_OVERRIDE)

    assert (
        store.lesson_completion_source(LESSON_PATH) is CompletionSource.MANUAL_OVERRIDE
    )


@pytest.mark.parametrize(
    "forged_source",
    (CompletionSource.LEGACY, CompletionSource.VALIDATED),
)
def test_manual_lesson_completion_rejects_forged_provenance(
    store: StateStore, forged_source: CompletionSource
) -> None:
    with pytest.raises(ValueError, match="manual override"):
        store.complete_lesson(*LESSON_PATH, source=forged_source)

    assert store.lesson_completion_source(LESSON_PATH) is None


def test_generic_completed_status_records_manual_override_provenance(
    store: StateStore,
) -> None:
    store.mark_lesson(*LESSON_PATH, ProgressStatus.COMPLETED)

    assert (
        store.lesson_completion_source(LESSON_PATH) is CompletionSource.MANUAL_OVERRIDE
    )


def _seed_two_passed_verifications(store: StateStore) -> None:
    store.start_step(STEP_PATH)
    store.record_verification_result(
        STEP_PATH,
        "check-os",
        passed=True,
        evidence="ok",
        validator_type=VerificationType.REMOTE_COMMAND,
    )
    store.record_verification_result(
        STEP_PATH,
        "check-agent",
        passed=True,
        evidence="ready",
        validator_type=VerificationType.PROVIDER_CHECK,
    )


class DatabaseAccessForbiddenStore(StateStore):
    def _connect(self) -> sqlite3.Connection:
        raise AssertionError("oversized evidence reached database access")


def test_default_migration_fences_open_writer_and_retires_legacy_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    environment_fixture: Callable[..., EnvironmentRecord],
) -> None:
    root = tmp_path / "state"
    legacy_path = root / "state.db"
    current_path = root / "learnlab.db"
    backup_path = root / "state.db.migrated"
    legacy = StateStore(legacy_path)
    legacy.initialize()
    legacy.create_environment(
        environment_fixture(
            id="existing-env",
            attempt_id=None,
            phase=EnvironmentPhase.RUNNING,
            vmid=102,
            provider_endpoint="https://proxmox.example.test:8006",
            provider_fingerprint="sha256:existing",
            expected_vm_name="learnlab-proxmox-admin-102",
        )
    )
    open_writer = sqlite3.connect(legacy_path, timeout=5.0, check_same_thread=False)
    install_reached = threading.Event()
    allow_install = threading.Event()
    writer_finished = threading.Event()
    migration_errors: list[BaseException] = []
    writer_outcome: list[str] = []
    real_link = state_module.os.link

    def controlled_link(source: Path, destination: Path) -> None:
        if Path(destination) == current_path:
            install_reached.set()
            if not allow_install.wait(timeout=5.0):
                raise TimeoutError("test did not release migration install")
        real_link(source, destination)

    def migrate() -> None:
        try:
            state_module.resolve_default_state_db(root)
        except BaseException as error:
            migration_errors.append(error)

    def write_late_environment() -> None:
        try:
            open_writer.execute(
                """
                INSERT INTO environments (
                    id, collection_id, course_id, lesson_id, attempt_id,
                    profile_name, provider_type, vmid, node, ip_address,
                    phase, upid, error_summary, created_at, updated_at,
                    provider_endpoint, provider_fingerprint,
                    expected_vm_name, clone_uncertain
                ) VALUES (
                    'late-env', 'proxmox', 'late-course', 'late-lesson', NULL,
                    'home-proxmox', 'proxmox', 103, 'pve02', NULL,
                    'running', NULL, NULL,
                    '2026-08-30T00:00:00Z', '2026-08-30T00:00:00Z',
                    'https://proxmox.example.test:8006', 'sha256:late',
                    'learnlab-late-course-103', 0
                )
                """
            )
            open_writer.commit()
            writer_outcome.append("committed")
        except sqlite3.Error as error:
            open_writer.rollback()
            writer_outcome.append(str(error))
        finally:
            open_writer.close()
            writer_finished.set()

    monkeypatch.setattr(state_module.os, "link", controlled_link)
    migration_thread = threading.Thread(target=migrate)
    writer_thread = threading.Thread(target=write_late_environment)
    migration_thread.start()
    assert install_reached.wait(timeout=5.0)
    writer_thread.start()
    writer_was_blocked = not writer_finished.wait(timeout=0.2)
    allow_install.set()
    migration_thread.join(timeout=5.0)
    writer_thread.join(timeout=5.0)

    assert not migration_thread.is_alive()
    assert not writer_thread.is_alive()
    assert migration_errors == []
    assert writer_was_blocked is True
    assert writer_outcome == ["legacy database migrated; reopen LearnLab"]
    assert [record.id for record in StateStore(current_path).list_environments()] == [
        "existing-env"
    ]
    with sqlite3.connect(current_path) as connection:
        current_triggers = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        ).fetchall()
    assert current_triggers == []
    with sqlite3.connect(backup_path) as connection:
        assert connection.execute("SELECT id FROM environments").fetchall() == [
            ("existing-env",)
        ]
        backup_triggers = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' ORDER BY name"
        ).fetchall()
        with pytest.raises(
            sqlite3.IntegrityError,
            match="legacy database migrated; reopen LearnLab",
        ):
            connection.execute(
                "UPDATE environments SET node = 'late-node' WHERE id = 'existing-env'"
            )
    assert len(backup_triggers) == 9


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
