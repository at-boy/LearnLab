"""Immutable curriculum models and loaders for on-disk course content."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from learnlab.errors import LearnLabError

_STABLE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class CurriculumError(LearnLabError):
    """Raised when curriculum files are malformed or inconsistent."""


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    content: str


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class Course:
    collection_id: str
    id: str
    title: str
    lessons: tuple[Lesson, ...]

    def first_incomplete(self, completed_ids: Set[str]) -> Lesson:
        """Return the first lesson whose ID has not been completed."""
        for lesson in self.lessons:
            if lesson.id not in completed_ids:
                return lesson
        raise CurriculumError(f"Course {self.id} has no incomplete lessons")


@dataclass(frozen=True)
class Collection:
    id: str
    title: str


@dataclass(frozen=True)
class CurriculumCatalog:
    collections_dir: Path

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
        _require_exact_keys(course_data, {"id", "title", "lessons"}, course_file)
        parsed_course_id = _required_id(course_data, "id", course_file)
        if parsed_course_id != course_id:
            raise CurriculumError(f"{course_file}: ID does not match directory")
        title = _required_string(course_data, "title", course_file)
        lesson_ids = _required_id_list(course_data, "lessons", course_file)

        lessons = tuple(
            self._load_lesson(course_dir, lesson_id) for lesson_id in lesson_ids
        )
        return Course(
            collection_id=collection.id,
            id=parsed_course_id,
            title=title,
            lessons=lessons,
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

    def _load_collection(self, path: Path) -> Collection:
        data = _load_mapping(path)
        _require_exact_keys(data, {"id", "title"}, path)
        return Collection(
            id=_required_id(data, "id", path),
            title=_required_string(data, "title", path),
        )

    def _load_lesson(self, course_dir: Path, lesson_id: str) -> Lesson:
        lessons_dir = course_dir / "lessons"
        lesson_dirs = list(lessons_dir.glob(f"*-{lesson_id}"))
        if len(lesson_dirs) != 1:
            raise CurriculumError(
                f"{lessons_dir}: expected one lesson directory for {lesson_id}"
            )
        lesson_dir = lesson_dirs[0]
        lesson_file = lesson_dir / "lesson.yaml"
        data = _load_mapping(lesson_file)
        _require_exact_keys(data, {"id", "title", "steps"}, lesson_file)
        parsed_lesson_id = _required_id(data, "id", lesson_file)
        if parsed_lesson_id != lesson_id or not lesson_dir.name.endswith(
            f"-{parsed_lesson_id}"
        ):
            raise CurriculumError(f"{lesson_file}: ID does not match directory")
        title = _required_string(data, "title", lesson_file)
        steps = _required_steps(data, lesson_file)
        return Lesson(id=parsed_lesson_id, title=title, steps=steps)


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as file:
            value = yaml.safe_load(file)
    except (OSError, yaml.YAMLError) as error:
        raise CurriculumError(f"{path}: unable to load curriculum") from error
    if not isinstance(value, dict):
        raise CurriculumError(f"{path}: expected a mapping root")
    if not all(isinstance(key, str) for key in value):
        raise CurriculumError(f"{path}: mapping keys must be strings")
    return value


def _require_exact_keys(
    data: Mapping[str, Any], expected: set[str], path: Path
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


def _required_id(data: Mapping[str, Any], key: str, path: Path) -> str:
    value = _required_string(data, key, path)
    if not _STABLE_ID.fullmatch(value):
        raise CurriculumError(f"{path}: {key} must be a stable ID")
    return value


def _required_string(data: Mapping[str, Any], key: str, path: Path) -> str:
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise CurriculumError(f"{path}: {key} must be a nonempty string")
    return value


def _required_id_list(data: Mapping[str, Any], key: str, path: Path) -> tuple[str, ...]:
    value = data[key]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CurriculumError(f"{path}: {key} must be an explicit list")
    ids = tuple(_validate_id(item, key, path) for item in value)
    if not ids:
        raise CurriculumError(f"{path}: {key} must not be empty")
    if len(set(ids)) != len(ids):
        raise CurriculumError(f"{path}: duplicate {key} IDs")
    return ids


def _required_steps(data: Mapping[str, Any], path: Path) -> tuple[Step, ...]:
    value = data["steps"]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CurriculumError(f"{path}: steps must be an explicit list")
    steps: list[Step] = []
    for item in value:
        if not isinstance(item, dict) or not all(isinstance(key, str) for key in item):
            raise CurriculumError(f"{path}: each step must be a mapping")
        _require_exact_keys(item, {"id", "title", "content"}, path)
        steps.append(
            Step(
                id=_required_id(item, "id", path),
                title=_required_string(item, "title", path),
                content=_required_string(item, "content", path),
            )
        )
    if not steps:
        raise CurriculumError(f"{path}: steps must not be empty")
    step_ids = [step.id for step in steps]
    if len(set(step_ids)) != len(step_ids):
        raise CurriculumError(f"{path}: duplicate step IDs")
    return tuple(steps)


def _validate_id(value: object, key: str, path: Path) -> str:
    if not isinstance(value, str) or not _STABLE_ID.fullmatch(value):
        raise CurriculumError(f"{path}: {key} entries must be stable IDs")
    return value
