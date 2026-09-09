from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import yaml

from learnlab.course_validation import (
    FindingSeverity,
    known_provider_checks,
    validate_catalog,
)
from learnlab.curriculum import CurriculumCatalog


def _write_course(
    root: Path,
    course_id: str,
    *,
    environment: dict[str, object] | None = None,
    verifications: list[dict[str, object]] | None = None,
) -> Path:
    collection = root / "demo"
    course = collection / "courses" / course_id
    lesson = course / "lessons" / "00-first"
    lesson.mkdir(parents=True, exist_ok=True)
    (collection / "collection.yaml").write_text(
        yaml.safe_dump({"id": "demo", "title": "Demo"}), encoding="utf-8"
    )
    (course / "course.yaml").write_text(
        yaml.safe_dump(
            {
                "id": course_id,
                "title": course_id.title(),
                "environment": environment or {"scope": "none"},
                "lessons": ["first"],
            }
        ),
        encoding="utf-8",
    )
    (lesson / "lesson.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "first",
                "title": "First",
                "steps": [
                    {
                        "id": "inspect",
                        "title": "Inspect",
                        "instructions": "Inspect it.",
                        "verifications": verifications
                        or [
                            {
                                "id": "answer",
                                "type": "text-evidence",
                                "prompt": "Answer",
                                "equals": "ok",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return course


def test_validation_aggregates_errors_from_independently_discoverable_courses(
    tmp_path: Path,
) -> None:
    root = tmp_path / "collections"
    first = _write_course(root, "bad-one")
    second = _write_course(root, "bad-two")
    (first / "course.yaml").write_text("id: WRONG\n", encoding="utf-8")
    (second / "course.yaml").write_text("title: Missing id\n", encoding="utf-8")

    report = validate_catalog(CurriculumCatalog(root))

    assert [finding.course_path for finding in report.errors] == [
        "demo/bad-one",
        "demo/bad-two",
    ]
    assert all(finding.code == "invalid-curriculum" for finding in report.errors)
    assert report.courses == ()


def test_validation_isolates_lesson_layout_errors_from_other_courses(
    tmp_path: Path,
) -> None:
    root = tmp_path / "collections"
    missing_lessons = _write_course(root, "bad-layout")
    invalid = _write_course(root, "bad-schema")
    _write_course(
        root,
        "linted",
        verifications=[
            {
                "id": "answer",
                "type": "text-evidence",
                "prompt": "Yes or no?",
                "matches": "yes|no",
            }
        ],
    )
    (missing_lessons / "lessons" / "00-first" / "lesson.yaml").unlink()
    (missing_lessons / "lessons" / "00-first").rmdir()
    (missing_lessons / "lessons").rmdir()
    (invalid / "course.yaml").write_text("id: bad-schema\n", encoding="utf-8")

    report = validate_catalog(CurriculumCatalog(root))

    assert [finding.course_path for finding in report.errors] == [
        "demo/bad-layout",
        "demo/bad-schema",
    ]
    assert [(finding.course_path, finding.code) for finding in report.warnings] == [
        ("demo/linted", "broad-yes-no-regex")
    ]
    assert [course.id for course in report.courses] == ["linted"]


def test_validation_reports_missing_catalog_as_a_finding(tmp_path: Path) -> None:
    report = validate_catalog(CurriculumCatalog(tmp_path / "missing"))

    actual = [
        (item.course_path, item.source_path, item.code) for item in report.errors
    ]
    assert actual == [("", ".", "invalid-catalog-layout")]


def test_validation_can_select_one_course(tmp_path: Path) -> None:
    root = tmp_path / "collections"
    _write_course(root, "first")
    _write_course(root, "second")

    report = validate_catalog(CurriculumCatalog(root), "demo/second")

    assert [course.id for course in report.courses] == ["second"]
    assert report.ok


def test_offline_validation_flags_only_the_six_authoring_lint_categories(
    tmp_path: Path,
) -> None:
    root = tmp_path / "collections"
    _write_course(
        root,
        "linted",
        environment={
            "scope": "course",
            "provider_capability": "proxmox.vm",
            "guest_capabilities": [],
        },
        verifications=[
            {
                "id": "broad",
                "type": "text-evidence",
                "prompt": "Yes or no?",
                "matches": "(?i)yes|no",
            },
            {
                "id": "interactive",
                "type": "remote-command",
                "command": "curl https://example.test && tail -f /var/log/messages",
            },
            {
                "id": "unknown",
                "type": "provider-check",
                "check": "future-check",
            },
            {
                "id": "manual",
                "type": "manual-confirmation",
                "prompt": "Confirm it.",
            },
        ],
    )

    report = validate_catalog(CurriculumCatalog(root))

    assert {finding.code for finding in report.warnings} == {
        "broad-yes-no-regex",
        "interactive-or-unbounded-command",
        "unknown-provider-check",
        "manual-confirmation-with-objective-check",
        "missing-os-capability",
        "undeclared-tool-capability",
    }
    assert len(report.warnings) == 6
    assert report.errors == ()


def test_effective_lesson_environment_is_linted(tmp_path: Path) -> None:
    root = tmp_path / "collections"
    course = _write_course(
        root,
        "override",
        environment={
            "scope": "course",
            "provider_capability": "proxmox.vm",
            "guest_capabilities": ["os.nixos", "tool.curl"],
        },
        verifications=[
            {
                "id": "curl",
                "type": "remote-command",
                "command": "curl --fail https://example.test",
            }
        ],
    )
    lesson_file = course / "lessons" / "00-first" / "lesson.yaml"
    lesson_data = yaml.safe_load(lesson_file.read_text(encoding="utf-8"))
    lesson_data["environment"] = {
        "scope": "lesson",
        "provider_capability": "proxmox.vm",
        "guest_capabilities": ["os.debian.13"],
    }
    lesson_file.write_text(yaml.safe_dump(lesson_data), encoding="utf-8")

    report = validate_catalog(CurriculumCatalog(root))

    assert [finding.code for finding in report.warnings] == [
        "undeclared-tool-capability"
    ]


def test_findings_are_deterministic_immutable_and_source_relative(
    tmp_path: Path,
) -> None:
    root = tmp_path / "collections"
    _write_course(
        root,
        "regex",
        verifications=[
            {
                "id": "answer",
                "type": "text-evidence",
                "prompt": "Yes or no?",
                "matches": "yes|no",
            }
        ],
    )

    first = validate_catalog(CurriculumCatalog(root))
    second = validate_catalog(CurriculumCatalog(root))

    assert first == second
    assert first.findings[0].severity is FindingSeverity.WARNING
    assert first.findings[0].source_path == (
        "demo/courses/regex/lessons/00-first/lesson.yaml"
    )
    with pytest.raises(FrozenInstanceError):
        first.findings[0].code = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("pattern", "warns"),
    [("^yes|no$", True), ("^(?:yes|no)$", False)],
)
def test_yes_no_regex_requires_anchors_around_the_complete_alternation(
    tmp_path: Path, pattern: str, warns: bool
) -> None:
    root = tmp_path / "collections"
    _write_course(
        root,
        "regex",
        verifications=[
            {
                "id": "answer",
                "type": "text-evidence",
                "prompt": "Yes or no?",
                "matches": pattern,
            }
        ],
    )

    report = validate_catalog(CurriculumCatalog(root))

    assert ("broad-yes-no-regex" in {item.code for item in report.warnings}) is warns


def test_provider_check_registry_is_static_and_matches_runtime() -> None:
    assert known_provider_checks() == frozenset(
        {"api-reachable", "template-visible", "vm-running", "guest-agent-ready"}
    )


def test_unsupported_provider_capability_is_an_error(tmp_path: Path) -> None:
    root = tmp_path / "collections"
    _write_course(
        root,
        "unsupported",
        environment={
            "scope": "course",
            "provider_capability": "future.vm",
            "guest_capabilities": ["os.nixos"],
        },
    )

    report = validate_catalog(CurriculumCatalog(root))

    assert [finding.code for finding in report.errors] == [
        "unsupported-provider-capability"
    ]
