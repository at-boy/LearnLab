from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from learnlab.course_certification import (
    CertificationError,
    CertificationRegistry,
    CourseMaturity,
    course_digest,
)


@pytest.fixture
def tmp_course(tmp_path: Path) -> Path:
    course = tmp_path / "admin"
    lesson = course / "lessons" / "00-first"
    lesson.mkdir(parents=True)
    (course / "course.yaml").write_text("id: admin\n", encoding="utf-8")
    (lesson / "lesson.yaml").write_text("id: first\n", encoding="utf-8")
    return course


def _write_registry(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        yaml.safe_dump({"certifications": records}, sort_keys=False), encoding="utf-8"
    )


def _record(digest: str, **changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "path": "demo/admin",
        "digest": digest,
        "status": "live-validated",
        "validated_at": "2026-09-09",
        "learnlab_revision": "09fe71f",
        "guest_capabilities": ["os.debian.13", "tool.curl"],
        "note": "Completed the acceptance checklist on a fresh guest.",
    }
    record.update(changes)
    return record


def test_course_digest_uses_relative_paths_and_file_bytes(tmp_course: Path) -> None:
    digest = course_digest(tmp_course)

    relocated = tmp_course.parent / "relocated"
    relocated.mkdir()
    (relocated / "lessons").mkdir()
    (relocated / "course.yaml").write_bytes((tmp_course / "course.yaml").read_bytes())
    (relocated / "lessons" / "00-first").mkdir()
    (relocated / "lessons" / "00-first" / "lesson.yaml").write_bytes(
        (tmp_course / "lessons" / "00-first" / "lesson.yaml").read_bytes()
    )

    assert course_digest(relocated) == digest
    (relocated / "course.yaml").write_text("id: changed\n", encoding="utf-8")
    assert course_digest(relocated) != digest


def test_changed_curriculum_invalidates_live_certificate(
    tmp_course: Path, tmp_path: Path
) -> None:
    digest = course_digest(tmp_course)
    registry_file = tmp_path / "certifications.yaml"
    _write_registry(registry_file, [_record(digest)])
    registry = CertificationRegistry.load(registry_file)

    assert registry.status("demo/admin", digest) is CourseMaturity.LIVE_VALIDATED

    (tmp_course / "course.yaml").write_text("changed", encoding="utf-8")
    assert (
        registry.status("demo/admin", course_digest(tmp_course)) is CourseMaturity.DRAFT
    )


def test_matching_offline_record_is_not_live_ready(
    tmp_course: Path, tmp_path: Path
) -> None:
    digest = course_digest(tmp_course)
    registry_file = tmp_path / "certifications.yaml"
    _write_registry(registry_file, [_record(digest, status="offline-validated")])

    assert (
        CertificationRegistry.load(registry_file).status("demo/admin", digest)
        is CourseMaturity.OFFLINE_VALIDATED
    )


@pytest.mark.parametrize(
    "record_change, message",
    [
        ({"extra": "value"}, "unknown keys"),
        ({"note": "Validated at https://lab.example.test"}, "non-secret"),
        ({"note": "Guest address 192.0.2.10"}, "non-secret"),
        ({"note": "Checked VMID 123"}, "non-secret"),
        ({"note": "Used token_secret value"}, "non-secret"),
    ],
)
def test_registry_rejects_unknown_or_infrastructure_metadata(
    tmp_course: Path,
    tmp_path: Path,
    record_change: dict[str, object],
    message: str,
) -> None:
    registry_file = tmp_path / "certifications.yaml"
    _write_registry(
        registry_file, [_record(course_digest(tmp_course), **record_change)]
    )

    with pytest.raises(CertificationError, match=message):
        CertificationRegistry.load(registry_file)


def test_registry_rejects_invalid_digest_and_date(
    tmp_course: Path, tmp_path: Path
) -> None:
    registry_file = tmp_path / "certifications.yaml"
    _write_registry(
        registry_file,
        [_record("not-sha256", validated_at="September 9")],
    )

    with pytest.raises(CertificationError, match="digest"):
        CertificationRegistry.load(registry_file)
