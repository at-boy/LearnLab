"""Immutable curriculum models and loaders for on-disk course content."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources.abc import Traversable
from typing import Any

import yaml

from learnlab.errors import LearnLabError

_STABLE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_CAPABILITY_ID = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*\Z")
_REQUIREMENTS_WARNING = "requirements is deprecated; use environment.guest_capabilities"
MAX_EVIDENCE_BYTES = 8 * 1024


class CurriculumError(LearnLabError):
    """Raised when curriculum files are malformed or inconsistent."""


class EnvironmentScope(StrEnum):
    """How long an environment declared by curriculum is retained."""

    COURSE = "course"
    LESSON = "lesson"
    NONE = "none"


class VerificationType(StrEnum):
    """The ordered checks a learner must complete for a step."""

    REMOTE_COMMAND = "remote-command"
    TEXT_EVIDENCE = "text-evidence"
    MANUAL_CONFIRMATION = "manual-confirmation"
    PROVIDER_CHECK = "provider-check"


@dataclass(frozen=True)
class EnvironmentPolicy:
    scope: EnvironmentScope
    provider_capability: str | None = None
    guest_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class Verification:
    id: str
    type: VerificationType
    failure_message: str | None = None
    command: str | None = None
    timeout_seconds: int | None = None
    prompt: str | None = None
    equals: str | None = None
    matches: str | None = None
    check: str | None = None


@dataclass(frozen=True, init=False)
class Step:
    id: str
    title: str
    instructions: str
    verifications: tuple[Verification, ...]

    def __init__(
        self,
        id: str,
        title: str,
        instructions: str | None = None,
        verifications: tuple[Verification, ...] = (),
        *,
        content: str | None = None,
    ) -> None:
        """Keep direct callers working while loaders expose instructions."""
        if instructions is not None and content is not None:
            raise TypeError("Step accepts instructions or content, not both")
        resolved_instructions = instructions if instructions is not None else content
        if resolved_instructions is None:
            raise TypeError("Step requires instructions")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "instructions", resolved_instructions)
        object.__setattr__(self, "verifications", verifications)

    @property
    def content(self) -> str:
        """Compatibility access for existing presentation callers."""
        return self.instructions


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    steps: tuple[Step, ...]
    environment: EnvironmentPolicy | None = None


@dataclass(frozen=True)
class Course:
    collection_id: str
    id: str
    title: str
    lessons: tuple[Lesson, ...]
    requirements: tuple[str, ...] = ()
    environment: EnvironmentPolicy = EnvironmentPolicy(EnvironmentScope.NONE)
    curriculum_warnings: tuple[str, ...] = ()

    def effective_environment(self, lesson: Lesson) -> EnvironmentPolicy:
        """Return the lesson override when present, otherwise the course policy."""
        return lesson.environment or self.environment

    def first_incomplete(self, completed_ids: Set[str]) -> Lesson:
        """Return the first lesson whose ID has not been completed."""
        for lesson in self.lessons:
            if lesson.id not in completed_ids:
                return lesson
        if self.lessons:
            return self.lessons[0]
        raise CurriculumError(f"Course {self.id} has no lessons")


@dataclass(frozen=True)
class Collection:
    id: str
    title: str


@dataclass(frozen=True)
class CourseSummary:
    collection_id: str
    course_id: str
    title: str

    @property
    def path(self) -> str:
        return f"{self.collection_id}/{self.course_id}"


@dataclass(frozen=True)
class CurriculumCatalog:
    collections_dir: Traversable

    def list_courses(self) -> tuple[CourseSummary, ...]:
        """Return every valid course in stable collection and course order."""
        summaries: list[CourseSummary] = []
        collection_dirs = sorted(
            _directory_children(self.collections_dir),
            key=lambda child: child.name,
        )
        for collection_dir in collection_dirs:
            collection = self._load_collection(collection_dir / "collection.yaml")
            if collection.id != collection_dir.name:
                raise CurriculumError(
                    f"{collection_dir / 'collection.yaml'}: ID does not match directory"
                )
            courses_dir = collection_dir / "courses"
            course_dirs = sorted(
                _directory_children(courses_dir),
                key=lambda child: child.name,
            )
            for course_dir in course_dirs:
                course = self.load_course(f"{collection.id}/{course_dir.name}")
                summaries.append(
                    CourseSummary(
                        collection_id=collection.id,
                        course_id=course.id,
                        title=course.title,
                    )
                )
        return tuple(summaries)

    def load_course(self, course_path: str) -> Course:
        """Load one collection/course path with its explicitly ordered lessons."""
        collection_id, course_id = self._split_course_path(course_path)
        collection_dir = self.collections_dir / collection_id
        collection = self._load_collection(collection_dir / "collection.yaml")
        if collection.id != collection_id:
            raise CurriculumError(
                f"{collection_dir / 'collection.yaml'}: ID does not match directory"
            )

        course_dir = collection_dir / "courses" / course_id
        course_file = course_dir / "course.yaml"
        course_data = _load_mapping(course_file)
        course_keys = {"id", "title", "lessons", "environment"}
        if "requirements" in course_data:
            course_keys.add("requirements")
        _require_exact_keys(course_data, course_keys, course_file)
        parsed_course_id = _required_id(course_data, "id", course_file)
        if parsed_course_id != course_id:
            raise CurriculumError(f"{course_file}: ID does not match directory")
        title = _required_string(course_data, "title", course_file)
        lesson_ids = _required_id_list(course_data, "lessons", course_file)
        environment = _required_environment(course_data, course_file)
        requirements = _optional_capabilities(course_data, course_file)
        curriculum_warnings: tuple[str, ...] = ()
        if "requirements" in course_data:
            if environment.scope is EnvironmentScope.NONE:
                raise CurriculumError(
                    f"{course_file}: requirements is forbidden for none "
                    "environment scope"
                )
            if "guest_capabilities" in course_data["environment"]:
                raise CurriculumError(
                    f"{course_file}: requirements cannot be combined with "
                    "environment.guest_capabilities"
                )
            environment = EnvironmentPolicy(
                scope=environment.scope,
                provider_capability=environment.provider_capability,
                guest_capabilities=requirements,
            )
            curriculum_warnings = (_REQUIREMENTS_WARNING,)

        lessons = tuple(
            self._load_lesson(course_dir, lesson_id, environment)
            for lesson_id in lesson_ids
        )
        return Course(
            collection_id=collection.id,
            id=parsed_course_id,
            title=title,
            lessons=lessons,
            requirements=requirements,
            environment=environment,
            curriculum_warnings=curriculum_warnings,
        )

    def _split_course_path(self, course_path: str) -> tuple[str, str]:
        pieces = course_path.split("/")
        if len(pieces) != 2 or not all(pieces):
            raise CurriculumError("Course path must use collection/course")
        collection_id, course_id = pieces
        if not _STABLE_ID.fullmatch(collection_id) or not _STABLE_ID.fullmatch(
            course_id
        ):
            raise CurriculumError("Course path must use collection/course")
        return collection_id, course_id

    def _load_collection(self, path: Traversable) -> Collection:
        data = _load_mapping(path)
        _require_exact_keys(data, {"id", "title"}, path)
        return Collection(
            id=_required_id(data, "id", path),
            title=_required_string(data, "title", path),
        )

    def _load_lesson(
        self,
        course_dir: Traversable,
        lesson_id: str,
        course_environment: EnvironmentPolicy,
    ) -> Lesson:
        lessons_dir = course_dir / "lessons"
        lesson_dirs = [
            child
            for child in lessons_dir.iterdir()
            if child.is_dir() and child.name.endswith(f"-{lesson_id}")
        ]
        if len(lesson_dirs) != 1:
            raise CurriculumError(
                f"{lessons_dir}: expected one lesson directory for {lesson_id}"
            )
        lesson_dir = lesson_dirs[0]
        lesson_file = lesson_dir / "lesson.yaml"
        data = _load_mapping(lesson_file)
        lesson_keys = {"id", "title", "steps"}
        if "environment" in data:
            lesson_keys.add("environment")
        _require_exact_keys(data, lesson_keys, lesson_file)
        parsed_lesson_id = _required_id(data, "id", lesson_file)
        if parsed_lesson_id != lesson_id or not lesson_dir.name.endswith(
            f"-{parsed_lesson_id}"
        ):
            raise CurriculumError(f"{lesson_file}: ID does not match directory")
        title = _required_string(data, "title", lesson_file)
        environment = _optional_environment(data, lesson_file)
        effective_environment = environment or course_environment
        steps = _required_steps(data, lesson_file, effective_environment)
        return Lesson(
            id=parsed_lesson_id,
            title=title,
            steps=steps,
            environment=environment,
        )


def _directory_children(path: Traversable) -> tuple[Traversable, ...]:
    try:
        return tuple(child for child in path.iterdir() if child.is_dir())
    except OSError as error:
        raise CurriculumError(f"{path}: expected a directory") from error


def _load_mapping(path: Traversable) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            value = yaml.safe_load(file)
    except (OSError, yaml.YAMLError) as error:
        raise CurriculumError(f"{path}: unable to load curriculum") from error
    if not isinstance(value, dict):
        raise CurriculumError(f"{path}: expected a mapping root")
    if not all(isinstance(key, str) for key in value):
        raise CurriculumError(f"{path}: mapping keys must be strings")
    return value


def _require_exact_keys(
    data: Mapping[str, Any], expected: set[str], path: Traversable
) -> None:
    if set(data) == expected:
        return
    details: list[str] = []
    missing = sorted(expected - set(data))
    unknown = sorted(set(data) - expected)
    if missing:
        details.append(f"missing keys: {', '.join(missing)}")
    if unknown:
        details.append(f"unknown keys: {', '.join(unknown)}")
    raise CurriculumError(f"{path}: {'; '.join(details)}")


def _required_id(data: Mapping[str, Any], key: str, path: Traversable) -> str:
    value = _required_string(data, key, path)
    if not _STABLE_ID.fullmatch(value):
        raise CurriculumError(f"{path}: {key} must be a stable ID")
    return value


def _required_string(data: Mapping[str, Any], key: str, path: Traversable) -> str:
    if key not in data:
        raise CurriculumError(f"{path}: missing key: {key}")
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise CurriculumError(f"{path}: {key} must be a nonempty string")
    return value


def _required_id_list(
    data: Mapping[str, Any], key: str, path: Traversable
) -> tuple[str, ...]:
    value = data[key]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CurriculumError(f"{path}: {key} must be an explicit list")
    ids = tuple(_validate_id(item, key, path) for item in value)
    if not ids:
        raise CurriculumError(f"{path}: {key} must not be empty")
    if len(set(ids)) != len(ids):
        raise CurriculumError(f"{path}: duplicate {key} IDs")
    return ids


def _required_steps(
    data: Mapping[str, Any], path: Traversable, environment: EnvironmentPolicy
) -> tuple[Step, ...]:
    value = data["steps"]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CurriculumError(f"{path}: steps must be an explicit list")
    steps: list[Step] = []
    for item in value:
        if not isinstance(item, dict) or not all(isinstance(key, str) for key in item):
            raise CurriculumError(f"{path}: each step must be a mapping")
        if "instructions" in item and "content" in item:
            raise CurriculumError(
                f"{path}: step content and instructions cannot both appear"
            )
        expected_keys = {"id", "title", "instructions", "verifications"}
        if "content" in item:
            expected_keys.remove("instructions")
            expected_keys.add("content")
        _require_exact_keys(item, expected_keys, path)
        instructions_key = "instructions" if "instructions" in item else "content"
        steps.append(
            Step(
                id=_required_id(item, "id", path),
                title=_required_string(item, "title", path),
                instructions=_required_string(item, instructions_key, path),
                verifications=_required_verifications(
                    item["verifications"], path, environment
                ),
            )
        )
    if not steps:
        raise CurriculumError(f"{path}: steps must not be empty")
    step_ids = [step.id for step in steps]
    if len(set(step_ids)) != len(step_ids):
        raise CurriculumError(f"{path}: duplicate step IDs")
    return tuple(steps)


def _required_environment(
    data: Mapping[str, Any], path: Traversable
) -> EnvironmentPolicy:
    return _parse_environment(data["environment"], path)


def _optional_environment(
    data: Mapping[str, Any], path: Traversable
) -> EnvironmentPolicy | None:
    if "environment" not in data:
        return None
    return _parse_environment(data["environment"], path)


def _parse_environment(value: object, path: Traversable) -> EnvironmentPolicy:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise CurriculumError(f"{path}: environment must be a mapping")
    keys = {"scope"}
    if "provider_capability" in value:
        keys.add("provider_capability")
    if "guest_capabilities" in value:
        keys.add("guest_capabilities")
    _require_exact_keys(value, keys, path)
    scope_value = _required_string(value, "scope", path)
    try:
        scope = EnvironmentScope(scope_value)
    except ValueError as error:
        raise CurriculumError(f"{path}: environment scope is invalid") from error

    if scope is EnvironmentScope.NONE:
        if "provider_capability" in value:
            raise CurriculumError(
                f"{path}: provider_capability is forbidden for none environment scope"
            )
        if "guest_capabilities" in value:
            raise CurriculumError(
                f"{path}: guest_capabilities is forbidden for none environment scope"
            )
        return EnvironmentPolicy(scope=scope)
    capability = value.get("provider_capability")
    if not isinstance(capability, str) or not _CAPABILITY_ID.fullmatch(capability):
        raise CurriculumError(
            f"{path}: provider_capability must be a capability ID for "
            f"{scope.value} environment scope"
        )
    guest_capabilities = _capability_list(
        value.get("guest_capabilities", ()), "guest_capabilities", path
    )
    return EnvironmentPolicy(
        scope=scope,
        provider_capability=capability,
        guest_capabilities=guest_capabilities,
    )


def _required_verifications(
    value: object, path: Traversable, environment: EnvironmentPolicy
) -> tuple[Verification, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CurriculumError(f"{path}: verifications must be an explicit list")
    verifications = tuple(
        _parse_verification(item, path, environment) for item in value
    )
    if not verifications:
        raise CurriculumError(f"{path}: verifications must not be empty")
    verification_ids = [verification.id for verification in verifications]
    if len(set(verification_ids)) != len(verification_ids):
        raise CurriculumError(f"{path}: duplicate verification id")
    return verifications


def _parse_verification(
    value: object, path: Traversable, environment: EnvironmentPolicy
) -> Verification:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise CurriculumError(f"{path}: each verification must be a mapping")
    verification_id = _required_id(value, "id", path)
    type_value = _required_string(value, "type", path)
    try:
        verification_type = VerificationType(type_value)
    except ValueError as error:
        raise CurriculumError(f"{path}: verification type is invalid") from error

    common_keys = {"id", "type", "failure_message"}
    type_keys = {
        VerificationType.REMOTE_COMMAND: {"command", "timeout_seconds"},
        VerificationType.TEXT_EVIDENCE: {"prompt", "equals", "matches"},
        VerificationType.MANUAL_CONFIRMATION: {"prompt"},
        VerificationType.PROVIDER_CHECK: {"check"},
    }
    all_typed_keys = set().union(*type_keys.values())
    forbidden = (set(value) & all_typed_keys) - type_keys[verification_type]
    if forbidden:
        raise CurriculumError(
            f"{path}: verification {verification_id}: forbidden fields for "
            f"{verification_type.value}: {', '.join(sorted(forbidden))}"
        )
    allowed = common_keys | type_keys[verification_type]
    _require_allowed_keys(value, allowed, path)

    failure_message = _optional_string(value, "failure_message", path)
    if verification_type is VerificationType.REMOTE_COMMAND:
        if environment.scope is EnvironmentScope.NONE:
            raise CurriculumError(
                f"{path}: verification {verification_id}: remote-command "
                "requires an environment"
            )
        command = _required_string(value, "command", path)
        timeout_seconds = _optional_timeout(value, path)
        return Verification(
            id=verification_id,
            type=verification_type,
            failure_message=failure_message,
            command=command,
            timeout_seconds=timeout_seconds,
        )
    if verification_type is VerificationType.TEXT_EVIDENCE:
        prompt = _required_string(value, "prompt", path)
        equals = _optional_string(value, "equals", path)
        matches = _optional_string(value, "matches", path)
        if (equals is None) == (matches is None):
            raise CurriculumError(
                f"{path}: verification {verification_id}: text-evidence "
                "requires exactly one of equals or matches"
            )
        if matches is not None:
            try:
                re.compile(matches)
            except re.error as error:
                raise CurriculumError(
                    f"{path}: verification {verification_id}: invalid "
                    "regular expression"
                ) from error
        return Verification(
            id=verification_id,
            type=verification_type,
            failure_message=failure_message,
            prompt=prompt,
            equals=equals,
            matches=matches,
        )
    if verification_type is VerificationType.MANUAL_CONFIRMATION:
        return Verification(
            id=verification_id,
            type=verification_type,
            failure_message=failure_message,
            prompt=_required_string(value, "prompt", path),
        )
    if environment.scope is EnvironmentScope.NONE:
        raise CurriculumError(
            f"{path}: verification {verification_id}: provider-check requires a "
            "provider and is forbidden for none environment scope"
        )
    return Verification(
        id=verification_id,
        type=verification_type,
        failure_message=failure_message,
        check=_required_string(value, "check", path),
    )


def _require_allowed_keys(
    data: Mapping[str, Any], allowed: set[str], path: Traversable
) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise CurriculumError(f"{path}: unknown keys: {', '.join(unknown)}")


def _optional_string(
    data: Mapping[str, Any], key: str, path: Traversable
) -> str | None:
    if key not in data:
        return None
    return _required_string(data, key, path)


def _optional_timeout(data: Mapping[str, Any], path: Traversable) -> int:
    value = data.get("timeout_seconds", 30)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 300:
        raise CurriculumError(
            f"{path}: timeout_seconds must be an integer from 1 to 300"
        )
    return int(value)


def _validate_id(value: object, key: str, path: Traversable) -> str:
    if not isinstance(value, str) or not _STABLE_ID.fullmatch(value):
        raise CurriculumError(f"{path}: {key} entries must be stable IDs")
    return value


def _optional_capabilities(
    data: Mapping[str, Any], path: Traversable
) -> tuple[str, ...]:
    return _capability_list(data.get("requirements", ()), "requirements", path)


def _capability_list(value: object, key: str, path: Traversable) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CurriculumError(f"{path}: {key} must be an explicit list")
    capabilities = tuple(value)
    if not all(
        isinstance(capability, str) and _CAPABILITY_ID.fullmatch(capability)
        for capability in capabilities
    ):
        raise CurriculumError(f"{path}: {key} entries must be capability IDs")
    if len(set(capabilities)) != len(capabilities):
        raise CurriculumError(f"{path}: duplicate {key} IDs")
    return capabilities
