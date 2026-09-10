"""Digest-bound maturity records for packaged course curriculum."""

from __future__ import annotations

import hashlib
import ipaddress
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from importlib.resources.abc import Traversable
from typing import Any

import yaml

from learnlab.errors import LearnLabError


class CertificationError(LearnLabError):
    """Raised when certification metadata is malformed or unsafe."""


class CourseMaturity(StrEnum):
    DRAFT = "draft"
    OFFLINE_VALIDATED = "offline-validated"
    LIVE_VALIDATED = "live-validated"


def course_digest(course_dir: Traversable) -> str:
    """Hash sorted relative paths and bytes for every file in a course tree."""
    digest = hashlib.sha256()
    for relative_path, file in sorted(_course_files(course_dir)):
        encoded_path = relative_path.encode("utf-8")
        try:
            with file.open("rb") as stream:
                contents = stream.read()
        except OSError as error:
            raise CertificationError(
                f"{course_dir}: unable to read course files"
            ) from error
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


def _course_files(
    directory: Traversable, prefix: str = ""
) -> list[tuple[str, Traversable]]:
    try:
        children = tuple(directory.iterdir())
    except OSError as error:
        raise CertificationError(f"{directory}: unable to read course files") from error
    files: list[tuple[str, Traversable]] = []
    for child in children:
        relative_path = f"{prefix}/{child.name}" if prefix else child.name
        if child.is_dir():
            files.extend(_course_files(child, relative_path))
        elif child.is_file():
            files.append((relative_path, child))
    return files


_RECORD_KEYS = {
    "path",
    "digest",
    "status",
    "validated_at",
    "learnlab_revision",
    "guest_capabilities",
    "note",
}
_COURSE_PATH = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CAPABILITY = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*\Z")
_FORBIDDEN_METADATA = re.compile(
    r"(?:\b(?:https?|ssh)://|\b(?:\d{1,3}\.){3}\d{1,3}\b|"
    r"\bvmid\b|\b(?:node|profile|endpoint|credentials?|password)\b|"
    r"\bprovider[._ -]+identity\b|\bapi[._ -]*key\b|"
    r"\b(?:token|secret)(?:[_ -]?(?:id|value|env|secret))?\b)",
    re.IGNORECASE,
)
_IP_CANDIDATE = re.compile(r"[0-9A-Fa-f:.]+")


@dataclass(frozen=True)
class CertificationRecord:
    path: str
    digest: str
    status: CourseMaturity
    validated_at: date
    learnlab_revision: str
    guest_capabilities: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class CertificationRegistry:
    records: Mapping[str, CertificationRecord]

    @classmethod
    def load(cls, path: Traversable) -> CertificationRegistry:
        try:
            with path.open("r", encoding="utf-8") as stream:
                data = yaml.safe_load(stream)
        except FileNotFoundError:
            return cls({})
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
            raise CertificationError(
                f"{path}: unable to load certifications"
            ) from error
        if not isinstance(data, Mapping) or set(data) != {"certifications"}:
            raise CertificationError(
                f"{path}: expected only a certifications mapping key"
            )
        entries = data["certifications"]
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            raise CertificationError(f"{path}: certifications must be a list")
        records: dict[str, CertificationRecord] = {}
        for index, entry in enumerate(entries):
            record = _parse_record(entry, path, index)
            if record.path in records:
                raise CertificationError(
                    f"{path}: duplicate certification path: {record.path}"
                )
            records[record.path] = record
        return cls(records)

    def status(self, course_path: str, digest: str) -> CourseMaturity:
        record = self.records.get(course_path)
        if record is None or record.digest != digest:
            return CourseMaturity.DRAFT
        return record.status


def _parse_record(
    value: object, source: Traversable, index: int
) -> CertificationRecord:
    label = f"{source}: certification {index + 1}"
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise CertificationError(f"{label}: expected a mapping")
    if set(value) != _RECORD_KEYS:
        unknown = sorted(set(value) - _RECORD_KEYS)
        missing = sorted(_RECORD_KEYS - set(value))
        details = []
        if missing:
            details.append(f"missing keys: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown keys: {', '.join(unknown)}")
        raise CertificationError(f"{label}: {'; '.join(details)}")

    for text in _string_values(value):
        if _contains_forbidden_metadata(text):
            raise CertificationError(f"{label}: metadata must be non-secret")

    strings = {
        key: _required_string(value, key, label)
        for key in (
            "path",
            "digest",
            "status",
            "learnlab_revision",
            "note",
        )
    }
    if not _COURSE_PATH.fullmatch(strings["path"]):
        raise CertificationError(f"{label}: path must use collection/course")
    if not _SHA256.fullmatch(strings["digest"]):
        raise CertificationError(f"{label}: digest must be a lowercase SHA-256")
    try:
        status = CourseMaturity(strings["status"])
    except ValueError as error:
        raise CertificationError(f"{label}: status is invalid") from error

    raw_date = value["validated_at"]
    if type(raw_date) is date:
        validated_at = raw_date
    elif isinstance(raw_date, str):
        try:
            validated_at = date.fromisoformat(raw_date)
        except ValueError as error:
            raise CertificationError(
                f"{label}: validated_at must be an ISO date"
            ) from error
    else:
        raise CertificationError(f"{label}: validated_at must be an ISO date")

    capabilities = value["guest_capabilities"]
    if not isinstance(capabilities, Sequence) or isinstance(capabilities, (str, bytes)):
        raise CertificationError(f"{label}: guest_capabilities must be a list")
    parsed_capabilities = tuple(capabilities)
    if not all(
        isinstance(capability, str) and _CAPABILITY.fullmatch(capability)
        for capability in parsed_capabilities
    ):
        raise CertificationError(f"{label}: guest capability is invalid")
    if len(set(parsed_capabilities)) != len(parsed_capabilities):
        raise CertificationError(f"{label}: duplicate guest capability")

    return CertificationRecord(
        path=strings["path"],
        digest=strings["digest"],
        status=status,
        validated_at=validated_at,
        learnlab_revision=strings["learnlab_revision"],
        guest_capabilities=parsed_capabilities,
        note=strings["note"],
    )


def _required_string(value: Mapping[str, Any], key: str, label: str) -> str:
    item = value[key]
    if not isinstance(item, str) or not item.strip():
        raise CertificationError(f"{label}: {key} must be a nonempty string")
    return item


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(
            text for item in value.values() for text in _string_values(item)
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(text for item in value for text in _string_values(item))
    return ()


def _contains_forbidden_metadata(value: str) -> bool:
    if _FORBIDDEN_METADATA.search(value):
        return True
    for match in _IP_CANDIDATE.finditer(value):
        candidate = match.group().strip("[](),.;")
        if not candidate or not (":" in candidate or "." in candidate):
            continue
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        return True
    return False
