from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from learnlab.curriculum import (
    MAX_EVIDENCE_BYTES,
    CurriculumCatalog,
    CurriculumError,
    EnvironmentScope,
    VerificationType,
)

REMOTE_A = {
    "id": "check-release",
    "type": "remote-command",
    "command": "test -f /etc/os-release",
}
REMOTE_B = {
    "id": "check-ssh",
    "type": "remote-command",
    "command": "systemctl is-active --quiet sshd",
}
TEXT_EVIDENCE = {
    "id": "explain-result",
    "type": "text-evidence",
    "prompt": "What does the operating system ID identify?",
    "matches": "(?i)linux",
}
PROVIDER_CHECK = {
    "id": "provider-visible",
    "type": "provider-check",
    "check": "vm-running",
}


class CurriculumBuilder:
    """Build a complete, small on-disk curriculum for loader tests."""

    def __init__(self, collections_dir: Path) -> None:
        self.collections_dir = collections_dir
        self.course_data: dict[str, Any] = {
            "id": "admin",
            "title": "Administration",
            "environment": {"scope": "course", "provider_capability": "proxmox.vm"},
            "lessons": ["first"],
        }
        self.lesson_data: dict[str, Any] = {
            "id": "first",
            "title": "First lesson",
            "steps": [
                {
                    "id": "inspect",
                    "title": "Inspect",
                    "instructions": "Inspect the system.",
                    "verifications": [REMOTE_A, REMOTE_B, TEXT_EVIDENCE],
                }
            ],
        }

    def course_environment(self, environment: dict[str, Any]) -> CurriculumBuilder:
        self.course_data["environment"] = environment
        return self

    def scope(self, scope: str) -> CurriculumBuilder:
        environment: dict[str, Any] = {"scope": scope}
        if scope != "none":
            environment["provider_capability"] = "proxmox.vm"
        return self.course_environment(environment)

    def lesson_environment(self, environment: dict[str, Any]) -> CurriculumBuilder:
        self.lesson_data["environment"] = environment
        return self

    def verifications(self, verifications: list[dict[str, Any]]) -> CurriculumBuilder:
        self.lesson_data["steps"][0]["verifications"] = verifications
        return self

    def load(self):
        collection_dir = self.collections_dir / "demo"
        course_dir = collection_dir / "courses" / "admin"
        lesson_dir = course_dir / "lessons" / "00-first"
        lesson_dir.mkdir(parents=True)
        (collection_dir / "collection.yaml").write_text(
            yaml.safe_dump({"id": "demo", "title": "Demo"}, sort_keys=False),
            encoding="utf-8",
        )
        (course_dir / "course.yaml").write_text(
            yaml.safe_dump(self.course_data, sort_keys=False), encoding="utf-8"
        )
        (lesson_dir / "lesson.yaml").write_text(
            yaml.safe_dump(self.lesson_data, sort_keys=False), encoding="utf-8"
        )
        return CurriculumCatalog(self.collections_dir).load_course("demo/admin")


@pytest.fixture
def curriculum_builder(tmp_path: Path) -> CurriculumBuilder:
    return CurriculumBuilder(tmp_path / "collections")


@pytest.fixture
def tmp_curriculum(curriculum_builder: CurriculumBuilder):
    curriculum_builder.lesson_environment({"scope": "none"}).verifications(
        [TEXT_EVIDENCE]
    )
    return curriculum_builder


@pytest.fixture
def collections_dir() -> Path:
    return Path(__file__).parents[1] / "src" / "learnlab" / "collections"


def _write_discovery_course(
    collections_dir: Path, collection_id: str, course_id: str, title: str
) -> None:
    collection_dir = collections_dir / collection_id
    course_dir = collection_dir / "courses" / course_id
    course_dir.mkdir(parents=True)
    (collection_dir / "collection.yaml").write_text(
        yaml.safe_dump(
            {"id": collection_id, "title": collection_id.title()}, sort_keys=False
        ),
        encoding="utf-8",
    )
    (course_dir / "course.yaml").write_text(
        yaml.safe_dump(
            {
                "id": course_id,
                "title": title,
                "lessons": ["first"],
                "environment": {"scope": "none"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    lesson_dir = course_dir / "lessons" / "00-first"
    lesson_dir.mkdir(parents=True)
    (lesson_dir / "lesson.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "first",
                "title": "First",
                "steps": [
                    {
                        "id": "read",
                        "title": "Read",
                        "instructions": "Read this.",
                        "verifications": [
                            {
                                "id": "confirm",
                                "type": "manual-confirmation",
                                "prompt": "Done?",
                            }
                        ],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_list_courses_is_complete_and_stably_sorted(tmp_path: Path) -> None:
    collections = tmp_path / "collections"
    _write_discovery_course(collections, "zeta", "last", "Last")
    _write_discovery_course(collections, "alpha", "two", "Two")
    _write_discovery_course(collections, "alpha", "one", "One")
    (collections / "ignored.txt").write_text("ignored", encoding="utf-8")

    catalog = CurriculumCatalog(collections)

    assert [item.path for item in catalog.list_courses()] == [
        "alpha/one",
        "alpha/two",
        "zeta/last",
    ]
    assert [item.title for item in catalog.list_courses()] == ["One", "Two", "Last"]


def test_list_courses_reports_malformed_collection(tmp_path: Path) -> None:
    collections = tmp_path / "collections"
    bad_collection = collections / "bad"
    bad_collection.mkdir(parents=True)
    (bad_collection / "collection.yaml").write_text("title: Bad\n", encoding="utf-8")

    with pytest.raises(CurriculumError, match=r"bad/collection\.yaml"):
        CurriculumCatalog(collections).list_courses()


def test_list_courses_reports_missing_collections_directory(tmp_path: Path) -> None:
    collections = tmp_path / "missing"

    with pytest.raises(CurriculumError, match=r"missing.*directory"):
        CurriculumCatalog(collections).list_courses()


@pytest.mark.parametrize("courses_entry", ["missing", "file"])
def test_list_courses_reports_invalid_courses_directory(
    tmp_path: Path, courses_entry: str
) -> None:
    collections = tmp_path / "collections"
    collection = collections / "alpha"
    collection.mkdir(parents=True)
    (collection / "collection.yaml").write_text(
        "id: alpha\ntitle: Alpha\n", encoding="utf-8"
    )
    if courses_entry == "file":
        (collection / "courses").write_text("not a directory", encoding="utf-8")

    with pytest.raises(CurriculumError, match=r"alpha/courses.*directory"):
        CurriculumCatalog(collections).list_courses()


def test_list_courses_reports_malformed_course(tmp_path: Path) -> None:
    collections = tmp_path / "collections"
    _write_discovery_course(collections, "alpha", "bad", "Bad")
    course_file = collections / "alpha" / "courses" / "bad" / "course.yaml"
    course_file.write_text("id: bad\ntitle: Bad\n", encoding="utf-8")

    with pytest.raises(CurriculumError, match=r"bad/course\.yaml"):
        CurriculumCatalog(collections).list_courses()


@pytest.fixture
def course(collections_dir: Path):
    return CurriculumCatalog(collections_dir).load_course("proxmox/proxmox-admin")


def test_loads_explicit_platform_hierarchy(collections_dir: Path):
    course = CurriculumCatalog(collections_dir).load_course("proxmox/proxmox-admin")

    assert course.collection_id == "proxmox"
    assert course.id == "proxmox-admin"
    assert [lesson.id for lesson in course.lessons] == ["api-access", "api-tokens"]
    assert [step.id for step in course.lessons[0].steps] == [
        "understand-api",
        "locate-endpoint",
    ]


def test_first_incomplete_follows_course_order(course):
    assert course.first_incomplete({"api-access"}).id == "api-tokens"


def test_first_incomplete_returns_first_lesson_when_all_are_completed(course):
    assert course.first_incomplete({"api-access", "api-tokens"}).id == "api-access"


def test_course_loads_abstract_capability_requirements(course):
    assert course.requirements == ("proxmox.api",)


def test_lesson_environment_override_wins_over_course(tmp_curriculum):
    loaded = tmp_curriculum.load()
    assert loaded.environment.scope is EnvironmentScope.COURSE
    assert (
        loaded.effective_environment(loaded.lessons[0]).scope is EnvironmentScope.NONE
    )


@pytest.mark.parametrize("scope", ["course", "lesson"])
def test_vm_scope_requires_provider_capability(
    scope: str, curriculum_builder: CurriculumBuilder
) -> None:
    curriculum_builder.course_environment({"scope": scope})

    with pytest.raises(CurriculumError, match="provider_capability"):
        curriculum_builder.load()


def test_none_scope_forbids_provider_capability(
    curriculum_builder: CurriculumBuilder,
) -> None:
    curriculum_builder.course_environment(
        {"scope": "none", "provider_capability": "proxmox.vm"}
    )

    with pytest.raises(CurriculumError, match="forbidden"):
        curriculum_builder.load()


def test_none_scope_forbids_null_provider_capability(
    curriculum_builder: CurriculumBuilder,
) -> None:
    curriculum_builder.course_environment(
        {"scope": "none", "provider_capability": None}
    )

    with pytest.raises(CurriculumError, match="forbidden"):
        curriculum_builder.load()


def test_step_accepts_repeated_validator_types_in_order(course):
    checks = course.lessons[0].steps[0].verifications
    assert [item.type for item in checks] == [
        VerificationType.REMOTE_COMMAND,
        VerificationType.REMOTE_COMMAND,
        VerificationType.PROVIDER_CHECK,
        VerificationType.PROVIDER_CHECK,
        VerificationType.TEXT_EVIDENCE,
        VerificationType.MANUAL_CONFIRMATION,
    ]


def test_duplicate_verification_ids_are_rejected(
    curriculum_builder: CurriculumBuilder,
) -> None:
    curriculum_builder.verifications([REMOTE_A, REMOTE_A])

    with pytest.raises(CurriculumError, match="duplicate verification id"):
        curriculum_builder.load()


def test_remote_command_is_rejected_for_effective_none_scope(
    curriculum_builder: CurriculumBuilder,
) -> None:
    curriculum_builder.scope("none").verifications([REMOTE_A])

    with pytest.raises(CurriculumError, match="requires an environment"):
        curriculum_builder.load()


def test_provider_check_is_rejected_for_course_none_scope(
    curriculum_builder: CurriculumBuilder,
) -> None:
    curriculum_builder.scope("none").verifications([PROVIDER_CHECK])

    with pytest.raises(CurriculumError, match="provider-check requires a provider"):
        curriculum_builder.load()


def test_provider_check_is_rejected_for_lesson_override_none_scope(
    curriculum_builder: CurriculumBuilder,
) -> None:
    curriculum_builder.lesson_environment({"scope": "none"}).verifications(
        [PROVIDER_CHECK]
    )

    with pytest.raises(CurriculumError, match="provider-check requires a provider"):
        curriculum_builder.load()


@pytest.mark.parametrize(
    ("verification", "message"),
    [
        ({"id": "check", "type": "remote-command"}, "command"),
        (
            {**REMOTE_A, "prompt": "Explain"},
            "forbidden",
        ),
        (
            {
                "id": "evidence",
                "type": "text-evidence",
                "prompt": "Explain",
            },
            "exactly one",
        ),
        (
            {**TEXT_EVIDENCE, "command": "hostname"},
            "forbidden",
        ),
        ({"id": "confirm", "type": "manual-confirmation"}, "prompt"),
        (
            {
                "id": "confirm",
                "type": "manual-confirmation",
                "prompt": "Review it",
                "check": "guest-agent-ready",
            },
            "forbidden",
        ),
        ({"id": "provider", "type": "provider-check"}, "check"),
        (
            {
                "id": "provider",
                "type": "provider-check",
                "check": "guest-agent-ready",
                "timeout_seconds": 10,
            },
            "forbidden",
        ),
    ],
)
def test_verification_type_schemas_require_and_forbid_fields(
    verification: dict[str, Any], message: str, curriculum_builder: CurriculumBuilder
) -> None:
    curriculum_builder.verifications([verification])

    with pytest.raises(CurriculumError, match=message):
        curriculum_builder.load()


@pytest.mark.parametrize(
    "verification",
    [
        {**TEXT_EVIDENCE, "equals": "linux"},
        {
            "id": "evidence",
            "type": "text-evidence",
            "prompt": "Explain",
            "equals": "linux",
            "matches": "linux",
        },
    ],
)
def test_text_evidence_requires_exactly_one_match_rule(
    verification: dict[str, Any], curriculum_builder: CurriculumBuilder
) -> None:
    curriculum_builder.verifications([verification])

    with pytest.raises(CurriculumError, match="exactly one"):
        curriculum_builder.load()


def test_text_evidence_rejects_invalid_regular_expression(
    curriculum_builder: CurriculumBuilder,
) -> None:
    curriculum_builder.verifications([{**TEXT_EVIDENCE, "matches": "("}])

    with pytest.raises(CurriculumError, match="regular expression"):
        curriculum_builder.load()


@pytest.mark.parametrize("timeout_seconds", [0, 301, True])
def test_remote_command_timeout_must_be_between_one_and_300_seconds(
    timeout_seconds: object, curriculum_builder: CurriculumBuilder
) -> None:
    curriculum_builder.verifications([{**REMOTE_A, "timeout_seconds": timeout_seconds}])

    with pytest.raises(CurriculumError, match="timeout_seconds"):
        curriculum_builder.load()


def test_remote_command_timeout_defaults_to_30_seconds(
    curriculum_builder: CurriculumBuilder,
) -> None:
    verification = (
        curriculum_builder.verifications([REMOTE_A])
        .load()
        .lessons[0]
        .steps[0]
        .verifications[0]
    )

    assert verification.timeout_seconds == 30


def test_text_evidence_limit_is_eight_kib() -> None:
    assert MAX_EVIDENCE_BYTES == 8 * 1024


@pytest.mark.parametrize(
    ("verifications", "message"),
    [
        ([], "verifications must not be empty"),
        ([{"id": "unknown", "type": "does-not-exist"}], "type"),
        ([{**REMOTE_A, "unknown": "value"}], "unknown keys"),
    ],
)
def test_step_rejects_invalid_verification_lists(
    verifications: list[dict[str, Any]],
    message: str,
    curriculum_builder: CurriculumBuilder,
) -> None:
    curriculum_builder.verifications(verifications)

    with pytest.raises(CurriculumError, match=message):
        curriculum_builder.load()


def test_content_is_a_loader_only_migration_alias(
    curriculum_builder: CurriculumBuilder,
) -> None:
    step = curriculum_builder.lesson_data["steps"][0]
    step["content"] = step.pop("instructions")

    loaded = curriculum_builder.load()

    assert loaded.lessons[0].steps[0].instructions == "Inspect the system."


def test_step_rejects_both_content_and_instructions(
    curriculum_builder: CurriculumBuilder,
) -> None:
    curriculum_builder.lesson_data["steps"][0]["content"] = "Legacy instructions"

    with pytest.raises(CurriculumError, match="content"):
        curriculum_builder.load()


@pytest.mark.parametrize("invalid_path", ["proxmox", "a/b/c", "/proxmox-admin"])
def test_course_path_requires_collection_slash_course(
    invalid_path: str, collections_dir: Path
):
    with pytest.raises(CurriculumError, match="collection/course"):
        CurriculumCatalog(collections_dir).load_course(invalid_path)


def test_curriculum_contains_no_provider_configuration_or_secret_material(
    collections_dir: Path,
):
    prohibited_text = {"token_secret", "PVEAPIToken=", "private-value"}
    prohibited_keys = {
        "template_vmid",
        "node",
        "storage",
        "network",
        "api_url",
        "provider_profile",
    }

    for path in collections_dir.rglob("*.yaml"):
        source = path.read_text(encoding="utf-8")
        assert not any(value in source for value in prohibited_text)
        parsed = yaml.safe_load(source)
        assert isinstance(parsed, dict)
        assert prohibited_keys.isdisjoint(parsed)


@pytest.mark.parametrize(
    "requirements",
    [
        "proxmox.api",
        ["Proxmox.API"],
        ["proxmox/api"],
        ["proxmox.api-"],
        ["proxmox.api", "proxmox.api"],
    ],
)
def test_course_rejects_invalid_capability_requirements(
    tmp_path: Path, collections_dir: Path, requirements: object
) -> None:
    destination = tmp_path / "collections"
    import shutil

    shutil.copytree(collections_dir, destination)
    course_file = destination / "proxmox" / "courses" / "proxmox-admin" / "course.yaml"
    parsed = yaml.safe_load(course_file.read_text(encoding="utf-8"))
    parsed["requirements"] = requirements
    course_file.write_text(yaml.safe_dump(parsed, sort_keys=False), encoding="utf-8")

    with pytest.raises(CurriculumError, match="requirements"):
        CurriculumCatalog(destination).load_course("proxmox/proxmox-admin")
