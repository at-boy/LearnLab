"""Transactional local progress and disposable-environment state."""

from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from learnlab.errors import LearnLabError


class StateConflictError(LearnLabError):
    """Raised when a requested state change would be unsafe."""


class ProgressStatus(StrEnum):
    """The local learning status for one lesson."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class EnvironmentPhase(StrEnum):
    """Persisted lifecycle boundaries for a disposable environment."""

    ALLOCATING = "allocating"
    CLONING = "cloning"
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    DELETING = "deleting"
    FAILED = "failed"


@dataclass(frozen=True)
class AttemptRecord:
    """One selected-lesson attempt."""

    id: str
    collection_id: str
    course_id: str
    lesson_id: str
    created_at: str


@dataclass(frozen=True)
class EnvironmentRecord:
    """The retained local record for one disposable environment."""

    id: str
    collection_id: str
    course_id: str
    lesson_id: str
    attempt_id: str | None
    profile_name: str
    provider_type: str
    phase: EnvironmentPhase
    vmid: int | None = None
    node: str | None = None
    ip_address: str | None = None
    upid: str | None = None
    error_summary: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    provider_endpoint: str = ""
    provider_fingerprint: str = ""
    expected_vm_name: str = ""
    clone_uncertain: bool = False


class StateStore:
    """SQLite-backed source of truth for progress and lifecycle state."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        """Create the durable schema and configure the database connection mode."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                for statement in _SCHEMA.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                _migrate_environment_columns(connection)
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
        finally:
            connection.close()

    def completed_lessons(self, collection_id: str, course_id: str) -> set[str]:
        """Return IDs whose local progress is explicitly completed."""
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT lesson_id
                FROM progress
                WHERE collection_id = ? AND course_id = ? AND status = ?
                """,
                (collection_id, course_id, ProgressStatus.COMPLETED.value),
            ).fetchall()
        finally:
            connection.close()
        return {str(row["lesson_id"]) for row in rows}

    def lesson_statuses(
        self, collection_id: str, course_id: str
    ) -> dict[str, ProgressStatus]:
        """Return every retained lesson status for one course."""
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT lesson_id, status
                FROM progress
                WHERE collection_id = ? AND course_id = ?
                """,
                (collection_id, course_id),
            ).fetchall()
        finally:
            connection.close()
        return {
            str(row["lesson_id"]): ProgressStatus(str(row["status"])) for row in rows
        }

    def list_progress(self) -> list[tuple[str, str, str, ProgressStatus]]:
        """Return every direct progress row for reset disclosure."""
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT collection_id, course_id, lesson_id, status
                FROM progress
                ORDER BY collection_id, course_id, lesson_id
                """
            ).fetchall()
        finally:
            connection.close()
        return [
            (
                str(row["collection_id"]),
                str(row["course_id"]),
                str(row["lesson_id"]),
                ProgressStatus(str(row["status"])),
            )
            for row in rows
        ]

    def start_lesson(self, collection_id: str, course_id: str, lesson_id: str) -> None:
        """Mark a lesson in progress after its environment starts."""
        self.mark_lesson(
            collection_id, course_id, lesson_id, ProgressStatus.IN_PROGRESS
        )

    def complete_lesson(
        self, collection_id: str, course_id: str, lesson_id: str
    ) -> None:
        """Mark a lesson completed only after an explicit user action."""
        self.mark_lesson(collection_id, course_id, lesson_id, ProgressStatus.COMPLETED)

    def mark_lesson(
        self,
        collection_id: str,
        course_id: str,
        lesson_id: str,
        status: ProgressStatus,
    ) -> None:
        """Persist a lesson's current status as one atomic update."""
        now = _utc_timestamp()
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    """
                    INSERT INTO progress (
                        collection_id, course_id, lesson_id, status,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(collection_id, course_id, lesson_id) DO UPDATE SET
                        status = excluded.status,
                        updated_at = excluded.updated_at
                    """,
                    (collection_id, course_id, lesson_id, status.value, now, now),
                )
        finally:
            connection.close()

    def create_attempt(
        self,
        collection_id: str,
        course_id: str,
        lesson_id: str,
        attempt_id: str | None = None,
    ) -> AttemptRecord:
        """Create and return an attempt for a selected lesson."""
        record = AttemptRecord(
            id=attempt_id or str(uuid.uuid4()),
            collection_id=collection_id,
            course_id=course_id,
            lesson_id=lesson_id,
            created_at=_utc_timestamp(),
        )
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    """
                    INSERT INTO attempts (
                        id, collection_id, course_id, lesson_id, created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.collection_id,
                        record.course_id,
                        record.lesson_id,
                        record.created_at,
                    ),
                )
        finally:
            connection.close()
        return record

    def list_attempts(self) -> list[AttemptRecord]:
        """Return retained attempts in creation order."""
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT id, collection_id, course_id, lesson_id, created_at
                FROM attempts
                ORDER BY created_at, id
                """
            ).fetchall()
        finally:
            connection.close()
        return [_row_to_attempt(row) for row in rows]

    def create_environment(self, environment: EnvironmentRecord) -> EnvironmentRecord:
        """Retain a new environment, rejecting a second record for its course."""
        now = _utc_timestamp()
        stored = replace(
            environment,
            created_at=now,
            updated_at=now,
        )
        connection = self._connect()
        try:
            try:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO environments (
                            id, collection_id, course_id, lesson_id, attempt_id,
                            profile_name, provider_type, vmid, node, ip_address,
                            phase, upid, error_summary, created_at, updated_at,
                            provider_endpoint, provider_fingerprint,
                            expected_vm_name, clone_uncertain
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )
                        """,
                        _environment_values(stored),
                    )
            except sqlite3.IntegrityError as error:
                if "environments.collection_id, environments.course_id" in str(error):
                    raise StateConflictError(
                        "Course already has an active environment; "
                        "run learnlab destroy first"
                    ) from error
                raise
        finally:
            connection.close()
        return stored

    def transition_environment(
        self, environment_id: str, phase: EnvironmentPhase, **fields: Any
    ) -> EnvironmentRecord:
        """Record one completed remote boundary and any returned safe metadata."""
        allowed_fields = {
            "vmid",
            "node",
            "ip_address",
            "upid",
            "error_summary",
            "clone_uncertain",
        }
        unknown_fields = set(fields) - allowed_fields
        if unknown_fields:
            unknown = ", ".join(sorted(unknown_fields))
            raise ValueError(f"Unsupported environment transition fields: {unknown}")

        values: list[object] = [phase.value, _utc_timestamp()]
        for field in (
            "vmid",
            "node",
            "ip_address",
            "upid",
            "error_summary",
            "clone_uncertain",
        ):
            values.extend((field in fields, fields.get(field)))
        values.append(environment_id)

        connection = self._connect()
        try:
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE environments SET
                        phase = ?,
                        updated_at = ?,
                        vmid = CASE WHEN ? THEN ? ELSE vmid END,
                        node = CASE WHEN ? THEN ? ELSE node END,
                        ip_address = CASE WHEN ? THEN ? ELSE ip_address END,
                        upid = CASE WHEN ? THEN ? ELSE upid END,
                        error_summary = CASE
                            WHEN ? THEN ? ELSE error_summary
                        END,
                        clone_uncertain = CASE
                            WHEN ? THEN ? ELSE clone_uncertain
                        END
                    WHERE id = ?
                    """,
                    values,
                )
                if cursor.rowcount != 1:
                    raise StateConflictError(
                        f"Environment does not exist: {environment_id}"
                    )
        finally:
            connection.close()
        record = self.get_environment(environment_id)
        if record is None:
            raise StateConflictError(f"Environment does not exist: {environment_id}")
        return record

    def record_clone_intent(
        self, environment_id: str, vmid: int, expected_vm_name: str
    ) -> EnvironmentRecord:
        """Durably bind one VMID/name before issuing the clone request."""
        connection = self._connect()
        try:
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE environments SET
                        phase = ?, vmid = ?, expected_vm_name = ?,
                        clone_uncertain = 1, updated_at = ?
                    WHERE id = ? AND expected_vm_name = ''
                    """,
                    (
                        EnvironmentPhase.CLONING.value,
                        vmid,
                        expected_vm_name,
                        _utc_timestamp(),
                        environment_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise StateConflictError(
                        f"Clone intent cannot be changed: {environment_id}"
                    )
        finally:
            connection.close()
        record = self.get_environment(environment_id)
        if record is None:
            raise StateConflictError(f"Environment does not exist: {environment_id}")
        return record

    def get_environment(self, environment_id: str) -> EnvironmentRecord | None:
        """Return one retained environment record, if present."""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM environments WHERE id = ?", (environment_id,)
            ).fetchone()
        finally:
            connection.close()
        return _row_to_environment(row) if row is not None else None

    def active_environment(
        self, collection_id: str, course_id: str
    ) -> EnvironmentRecord | None:
        """Return the one retained environment for a course, if any."""
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT * FROM environments
                WHERE collection_id = ? AND course_id = ?
                """,
                (collection_id, course_id),
            ).fetchone()
        finally:
            connection.close()
        return _row_to_environment(row) if row is not None else None

    def list_environments(self) -> list[EnvironmentRecord]:
        """Return every retained environment in creation order."""
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM environments ORDER BY created_at, id"
            ).fetchall()
        finally:
            connection.close()
        return [_row_to_environment(row) for row in rows]

    def delete_environment(self, environment_id: str) -> None:
        """Remove a record after lifecycle cleanup confirmed remote absence."""
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    "DELETE FROM environments WHERE id = ?", (environment_id,)
                )
        finally:
            connection.close()

    def reset_scope(self, collection_id: str, course_id: str | None = None) -> None:
        """Delete progress and attempts only when the scope has no environments."""
        parameters: tuple[str, ...]
        if course_id is None:
            environment_query = (
                "SELECT 1 FROM environments WHERE collection_id = ? LIMIT 1"
            )
            progress_query = "DELETE FROM progress WHERE collection_id = ?"
            attempts_query = "DELETE FROM attempts WHERE collection_id = ?"
            parameters = (collection_id,)
        else:
            environment_query = (
                "SELECT 1 FROM environments "
                "WHERE collection_id = ? AND course_id = ? LIMIT 1"
            )
            progress_query = (
                "DELETE FROM progress WHERE collection_id = ? AND course_id = ?"
            )
            attempts_query = (
                "DELETE FROM attempts WHERE collection_id = ? AND course_id = ?"
            )
            parameters = (collection_id, course_id)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(environment_query, parameters).fetchone()
                if existing is not None:
                    raise StateConflictError(
                        "Run learnlab destroy for matching environments before "
                        "resetting progress"
                    )
                connection.execute(progress_query, parameters)
                connection.execute(attempts_query, parameters)
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
        finally:
            connection.close()

    def erase_all(self, preserve_completed: bool) -> None:
        """Clear attempts and optionally retain only completed progress records."""
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT 1 FROM environments LIMIT 1"
                ).fetchone()
                if existing is not None:
                    raise StateConflictError(
                        "Destroy retained environments before erasing local state"
                    )
                connection.execute("DELETE FROM attempts")
                if preserve_completed:
                    connection.execute(
                        "DELETE FROM progress WHERE status != ?",
                        (ProgressStatus.COMPLETED.value,),
                    )
                else:
                    connection.execute("DELETE FROM progress")
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _environment_values(environment: EnvironmentRecord) -> tuple[object, ...]:
    return (
        environment.id,
        environment.collection_id,
        environment.course_id,
        environment.lesson_id,
        environment.attempt_id,
        environment.profile_name,
        environment.provider_type,
        environment.vmid,
        environment.node,
        environment.ip_address,
        environment.phase.value,
        environment.upid,
        environment.error_summary,
        environment.created_at,
        environment.updated_at,
        environment.provider_endpoint,
        environment.provider_fingerprint,
        environment.expected_vm_name,
        int(environment.clone_uncertain),
    )


def _row_to_attempt(row: sqlite3.Row) -> AttemptRecord:
    return AttemptRecord(
        id=str(row["id"]),
        collection_id=str(row["collection_id"]),
        course_id=str(row["course_id"]),
        lesson_id=str(row["lesson_id"]),
        created_at=str(row["created_at"]),
    )


def _row_to_environment(row: sqlite3.Row) -> EnvironmentRecord:
    return EnvironmentRecord(
        id=str(row["id"]),
        collection_id=str(row["collection_id"]),
        course_id=str(row["course_id"]),
        lesson_id=str(row["lesson_id"]),
        attempt_id=_optional_string(row["attempt_id"]),
        profile_name=str(row["profile_name"]),
        provider_type=str(row["provider_type"]),
        phase=EnvironmentPhase(str(row["phase"])),
        vmid=int(row["vmid"]) if row["vmid"] is not None else None,
        node=_optional_string(row["node"]),
        ip_address=_optional_string(row["ip_address"]),
        upid=_optional_string(row["upid"]),
        error_summary=_optional_string(row["error_summary"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        provider_endpoint=str(row["provider_endpoint"]),
        provider_fingerprint=str(row["provider_fingerprint"]),
        expected_vm_name=str(row["expected_vm_name"]),
        clone_uncertain=bool(row["clone_uncertain"]),
    )


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None


def resolve_default_state_db(state_root: Path) -> Path:
    """Resolve or safely migrate the CLI's historical default database."""
    current = state_root / "learnlab.db"
    legacy = state_root / "state.db"
    backup = state_root / "state.db.migrated"
    temporary = state_root / ".learnlab.db.migrating"
    temporary_artifacts = (
        temporary,
        temporary.with_name(f"{temporary.name}-wal"),
        temporary.with_name(f"{temporary.name}-shm"),
        temporary.with_name(f"{temporary.name}-journal"),
    )
    orphaned_database_sidecars = tuple(
        sidecar
        for database in (current, legacy)
        if not database.exists()
        for suffix in ("-wal", "-shm", "-journal")
        if (sidecar := database.with_name(f"{database.name}{suffix}")).exists()
    )

    if current.exists() and legacy.exists():
        raise _state_migration_conflict((legacy, current))
    if any(path.exists() for path in temporary_artifacts):
        raise _state_migration_conflict(
            tuple(path for path in temporary_artifacts if path.exists())
        )
    if orphaned_database_sidecars:
        raise _state_migration_conflict(orphaned_database_sidecars)
    if legacy.exists() and backup.exists():
        raise _state_migration_conflict((legacy, backup))
    if not current.exists() and not legacy.exists() and backup.exists():
        raise _state_migration_conflict((backup,))
    for path in (current, legacy, backup):
        if path.exists() and not path.is_file():
            raise _state_migration_conflict((path,))
    if current.exists():
        return current
    if not legacy.exists():
        return current

    _migrate_legacy_default_db(legacy, current, backup, temporary)
    return current


def _migrate_legacy_default_db(
    legacy: Path,
    current: Path,
    backup: Path,
    temporary: Path,
) -> None:
    migration_lock: sqlite3.Connection | None = None
    try:
        migration_lock = sqlite3.connect(legacy)
        migration_lock.execute("BEGIN IMMEDIATE")
        try:
            _install_legacy_retirement_triggers(migration_lock)
        except BaseException:
            migration_lock.rollback()
            raise
        else:
            migration_lock.commit()

        # The committed triggers retire writers that raced between these two
        # transactions. This second writer lock fences the snapshot through the
        # durable installation of the new authoritative database.
        migration_lock.execute("BEGIN IMMEDIATE")
        temporary.open("xb").close()
        snapshot_source = sqlite3.connect(legacy)
        try:
            destination = sqlite3.connect(temporary)
            try:
                snapshot_source.backup(destination)
                _remove_legacy_retirement_triggers(destination)
                destination.commit()
            finally:
                destination.close()
        finally:
            snapshot_source.close()

        StateStore(temporary).initialize()
        migrated = sqlite3.connect(temporary)
        try:
            _require_complete_checkpoint(migrated, temporary, truncate=True)
        finally:
            migrated.close()
        _remove_empty_temporary_sidecars(temporary)
        temporary.chmod(legacy.stat().st_mode & 0o777)
        with temporary.open("rb") as migrated_file:
            os.fsync(migrated_file.fileno())

        os.link(temporary, current)
        _sync_directory(current.parent)
        temporary.unlink()
        _sync_directory(current.parent)

        migration_lock.commit()
        _require_complete_checkpoint(migration_lock, legacy)
        migration_lock.close()
        migration_lock = None

        os.link(legacy, backup)
        _sync_directory(current.parent)
        legacy.unlink()
        _sync_directory(current.parent)
    except (OSError, sqlite3.Error) as error:
        if migration_lock is not None:
            if migration_lock.in_transaction:
                migration_lock.rollback()
            migration_lock.close()
        raise StateConflictError(
            "State database migration stopped safely and requires manual recovery. "
            f"Preserve {legacy}, {current}, {backup}, and {temporary}; inspect which "
            "files exist, then leave exactly one authoritative database at "
            f"{current} before retrying."
        ) from error


def _install_legacy_retirement_triggers(connection: sqlite3.Connection) -> None:
    for statement in _LEGACY_RETIREMENT_TRIGGER_SQL:
        connection.execute(statement)


def _remove_legacy_retirement_triggers(connection: sqlite3.Connection) -> None:
    for statement in _LEGACY_RETIREMENT_TRIGGER_DROP_SQL:
        connection.execute(statement)


def _require_complete_checkpoint(
    connection: sqlite3.Connection, path: Path, *, truncate: bool = False
) -> None:
    if truncate:
        result = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    else:
        result = connection.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
    if (
        result is None
        or len(result) != 3
        or int(result[0]) != 0
        or int(result[1]) != int(result[2])
    ):
        raise sqlite3.OperationalError(f"Unable to checkpoint state database {path}")


def _remove_empty_temporary_sidecars(temporary: Path) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar = temporary.with_name(f"{temporary.name}{suffix}")
        if not sidecar.exists():
            continue
        if suffix == "-wal" and sidecar.stat().st_size != 0:
            raise sqlite3.OperationalError(
                f"Migration WAL was not empty after checkpoint: {sidecar}"
            )
        sidecar.unlink()


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _state_migration_conflict(paths: tuple[Path, ...]) -> StateConflictError:
    rendered_paths = ", ".join(str(path) for path in paths)
    return StateConflictError(
        "State database files require manual recovery; no state was changed. "
        f"Found: {rendered_paths}. Preserve copies and inspect which database is "
        "authoritative, then leave exactly one authoritative database at "
        f"{paths[0].parent / 'learnlab.db'} and move other database or migration "
        "artifacts outside the state directory before retrying."
    )


def _migrate_environment_columns(connection: sqlite3.Connection) -> None:
    columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(environments)")
    }
    if "provider_endpoint" not in columns:
        connection.execute(
            "ALTER TABLE environments "
            "ADD COLUMN provider_endpoint TEXT NOT NULL DEFAULT ''"
        )
    if "provider_fingerprint" not in columns:
        connection.execute(
            "ALTER TABLE environments "
            "ADD COLUMN provider_fingerprint TEXT NOT NULL DEFAULT ''"
        )
    if "expected_vm_name" not in columns:
        connection.execute(
            "ALTER TABLE environments "
            "ADD COLUMN expected_vm_name TEXT NOT NULL DEFAULT ''"
        )
    if "clone_uncertain" not in columns:
        connection.execute(
            "ALTER TABLE environments "
            "ADD COLUMN clone_uncertain INTEGER NOT NULL DEFAULT 0"
        )


_LEGACY_RETIREMENT_TRIGGER_SQL = (
    """
    CREATE TRIGGER IF NOT EXISTS learnlab_retired_progress_insert
    BEFORE INSERT ON progress
    BEGIN
        SELECT RAISE(ABORT, 'legacy database migrated; reopen LearnLab');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS learnlab_retired_progress_update
    BEFORE UPDATE ON progress
    BEGIN
        SELECT RAISE(ABORT, 'legacy database migrated; reopen LearnLab');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS learnlab_retired_progress_delete
    BEFORE DELETE ON progress
    BEGIN
        SELECT RAISE(ABORT, 'legacy database migrated; reopen LearnLab');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS learnlab_retired_attempts_insert
    BEFORE INSERT ON attempts
    BEGIN
        SELECT RAISE(ABORT, 'legacy database migrated; reopen LearnLab');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS learnlab_retired_attempts_update
    BEFORE UPDATE ON attempts
    BEGIN
        SELECT RAISE(ABORT, 'legacy database migrated; reopen LearnLab');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS learnlab_retired_attempts_delete
    BEFORE DELETE ON attempts
    BEGIN
        SELECT RAISE(ABORT, 'legacy database migrated; reopen LearnLab');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS learnlab_retired_environments_insert
    BEFORE INSERT ON environments
    BEGIN
        SELECT RAISE(ABORT, 'legacy database migrated; reopen LearnLab');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS learnlab_retired_environments_update
    BEFORE UPDATE ON environments
    BEGIN
        SELECT RAISE(ABORT, 'legacy database migrated; reopen LearnLab');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS learnlab_retired_environments_delete
    BEFORE DELETE ON environments
    BEGIN
        SELECT RAISE(ABORT, 'legacy database migrated; reopen LearnLab');
    END
    """,
)

_LEGACY_RETIREMENT_TRIGGER_DROP_SQL = (
    "DROP TRIGGER IF EXISTS learnlab_retired_progress_insert",
    "DROP TRIGGER IF EXISTS learnlab_retired_progress_update",
    "DROP TRIGGER IF EXISTS learnlab_retired_progress_delete",
    "DROP TRIGGER IF EXISTS learnlab_retired_attempts_insert",
    "DROP TRIGGER IF EXISTS learnlab_retired_attempts_update",
    "DROP TRIGGER IF EXISTS learnlab_retired_attempts_delete",
    "DROP TRIGGER IF EXISTS learnlab_retired_environments_insert",
    "DROP TRIGGER IF EXISTS learnlab_retired_environments_update",
    "DROP TRIGGER IF EXISTS learnlab_retired_environments_delete",
)


_PROGRESS_VALUES = ", ".join(f"'{status.value}'" for status in ProgressStatus)
_PHASE_VALUES = ", ".join(f"'{phase.value}'" for phase in EnvironmentPhase)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS progress (
    collection_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    lesson_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ({_PROGRESS_VALUES})),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (collection_id, course_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    lesson_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS environments (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    lesson_id TEXT NOT NULL,
    attempt_id TEXT REFERENCES attempts(id) ON DELETE RESTRICT,
    profile_name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    vmid INTEGER CHECK (vmid IS NULL OR vmid > 0),
    node TEXT,
    ip_address TEXT,
    phase TEXT NOT NULL CHECK (phase IN ({_PHASE_VALUES})),
    upid TEXT,
    error_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    provider_endpoint TEXT NOT NULL DEFAULT '',
    provider_fingerprint TEXT NOT NULL DEFAULT '',
    expected_vm_name TEXT NOT NULL DEFAULT '',
    clone_uncertain INTEGER NOT NULL DEFAULT 0 CHECK (clone_uncertain IN (0, 1))
);

CREATE UNIQUE INDEX IF NOT EXISTS one_retained_environment_per_course
ON environments (collection_id, course_id)
WHERE phase IN ({_PHASE_VALUES});
"""
