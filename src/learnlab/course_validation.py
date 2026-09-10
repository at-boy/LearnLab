"""Deterministic, side-effect-free validation of complete curriculum catalogs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources.abc import Traversable
from pathlib import Path

from learnlab.config import ProxmoxProfile
from learnlab.course_certification import CertificationError
from learnlab.curriculum import (
    Course,
    CurriculumCatalog,
    CurriculumError,
    EnvironmentPolicy,
    EnvironmentScope,
    VerificationType,
)
from learnlab.providers.base import ProviderHealth
from learnlab.providers.proxmox import known_provider_checks

_SUPPORTED_PROVIDER_CAPABILITIES = frozenset({"proxmox.vm"})
_TOOL_COMMANDS = {"curl": "tool.curl", "git": "tool.git", "wget": "tool.wget"}
_UNBOUNDED_COMMAND = re.compile(
    r"(?:^|[;&|]\s*)(?:bash|sh|ssh|top|less|more|vi|vim|nano|watch|read)(?:\s|$)"
    r"|(?:^|\s)(?:tail|journalctl)\s+[^;&|]*(?:-[^-\s]*f|--follow)(?:\s|$)"
)


class FindingSeverity(StrEnum):
    """Severity used by curriculum validation output."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class CurriculumFinding:
    """One source-relative, actionable curriculum finding."""

    severity: FindingSeverity
    course_path: str
    source_path: str
    code: str
    message: str
    remedy: str


@dataclass(frozen=True)
class ValidationReport:
    """Immutable result plus loaded courses for later compatibility checks."""

    findings: tuple[CurriculumFinding, ...] = ()
    courses: tuple[Course, ...] = ()
    operational_failure: bool = False

    @property
    def errors(self) -> tuple[CurriculumFinding, ...]:
        return tuple(
            finding
            for finding in self.findings
            if finding.severity is FindingSeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[CurriculumFinding, ...]:
        return tuple(
            finding
            for finding in self.findings
            if finding.severity is FindingSeverity.WARNING
        )

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_profile_compatibility(
    report: ValidationReport,
    profile: ProxmoxProfile,
    health: ProviderHealth,
) -> ValidationReport:
    """Add safe, read-only profile compatibility findings to a static report."""
    findings = list(report.findings)
    available = frozenset(profile.template_capabilities)
    for course in report.courses:
        required = frozenset(
            capability
            for lesson in course.lessons
            for capability in course.effective_environment(lesson).guest_capabilities
        )
        course_path = f"{course.collection_id}/{course.id}"
        for capability in sorted(required - available):
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    course_path,
                    _course_source(course_path),
                    "missing-guest-capability",
                    f"The provider template does not declare {capability!r}.",
                    "Add the capability to the selected profile's "
                    "template_capabilities or select a compatible profile.",
                )
            )

    failed_checks = tuple(
        check for check in health.checks if check.required and not check.ok
    )
    operational_failure = report.operational_failure or bool(
        health.provider_error or failed_checks
    )
    for check in failed_checks:
        findings.append(
            _finding(
                FindingSeverity.ERROR,
                "",
                ".",
                "provider-health-failed",
                f"Provider prerequisite {_safe_health_label(check.name)!r} failed.",
                "Check the selected profile and provider access, then retry.",
            )
        )
    if health.provider_error and not failed_checks:
        findings.append(
            _finding(
                FindingSeverity.ERROR,
                "",
                ".",
                "provider-health-failed",
                "The provider health check could not complete.",
                "Check the selected profile and provider access, then retry.",
            )
        )

    return ValidationReport(
        findings=tuple(sorted(set(findings), key=_finding_key)),
        courses=report.courses,
        operational_failure=operational_failure,
    )


def _safe_health_label(name: str) -> str:
    labels = {
        "API": "API",
        "Authentication": "Authentication",
        "Node": "Node",
        "Template identity": "Template identity",
        "Storage": "Storage",
        "Network": "Network",
    }
    return labels.get(name, "Provider prerequisite")


def validate_catalog(
    catalog: CurriculumCatalog, course_path: str | None = None
) -> ValidationReport:
    """Validate selected curriculum without configuration, state, or provider access."""
    findings: list[CurriculumFinding] = []
    courses: list[Course] = []
    root = catalog.collections_dir

    candidates: tuple[tuple[str, str], ...]
    if course_path is not None:
        candidates = ((course_path, _course_source(course_path)),)
    else:
        candidates = _discover_courses(root, findings)

    for candidate, default_source in candidates:
        try:
            course = catalog.load_course(candidate)
        except CertificationError as error:
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    candidate,
                    _source_from_error(error, root, default_source),
                    "invalid-certification",
                    _relative_message(error, root),
                    "Correct certifications.yaml metadata and ensure the registry "
                    "and course files are readable, then retry offline validation.",
                )
            )
            continue
        except (CurriculumError, OSError) as error:
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    candidate,
                    _source_from_error(error, root, default_source),
                    "invalid-curriculum",
                    _relative_message(error, root),
                    "Correct the curriculum schema, identifiers, and directory layout.",
                )
            )
            continue
        courses.append(course)
        findings.extend(_validate_course(course, root))

    return ValidationReport(
        findings=tuple(sorted(set(findings), key=_finding_key)),
        courses=tuple(sorted(courses, key=lambda item: (item.collection_id, item.id))),
    )


def _discover_courses(
    root: Traversable, findings: list[CurriculumFinding]
) -> tuple[tuple[str, str], ...]:
    try:
        collection_dirs = sorted(
            (child for child in root.iterdir() if child.is_dir()),
            key=lambda child: child.name,
        )
    except OSError:
        findings.append(
            _finding(
                FindingSeverity.ERROR,
                "",
                ".",
                "invalid-catalog-layout",
                "The curriculum catalog is missing or is not a readable directory.",
                "Create a readable collections directory with collection "
                "subdirectories.",
            )
        )
        return ()

    candidates: list[tuple[str, str]] = []
    for collection_dir in collection_dirs:
        collection_id = collection_dir.name
        collection_source = f"{collection_id}/collection.yaml"
        try:
            collection = CurriculumCatalog(root)._load_collection(  # noqa: SLF001
                collection_dir / "collection.yaml"
            )
            if collection.id != collection_id:
                raise CurriculumError(
                    f"{collection_dir / 'collection.yaml'}: ID does not match directory"
                )
        except CurriculumError as error:
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    collection_id,
                    collection_source,
                    "invalid-catalog-layout",
                    _relative_message(error, root),
                    "Correct the collection schema and make its ID match the "
                    "directory.",
                )
            )
            continue

        courses_dir = collection_dir / "courses"
        try:
            course_dirs = sorted(
                (child for child in courses_dir.iterdir() if child.is_dir()),
                key=lambda child: child.name,
            )
        except OSError:
            findings.append(
                _finding(
                    FindingSeverity.ERROR,
                    collection_id,
                    f"{collection_id}/courses",
                    "invalid-catalog-layout",
                    "The collection courses entry is missing or is not a directory.",
                    "Create a courses directory containing one directory per course.",
                )
            )
            continue
        candidates.extend(
            (
                f"{collection_id}/{course_dir.name}",
                f"{collection_id}/courses/{course_dir.name}/course.yaml",
            )
            for course_dir in course_dirs
        )
    return tuple(candidates)


def _validate_course(course: Course, root: Traversable) -> list[CurriculumFinding]:
    course_path = f"{course.collection_id}/{course.id}"
    course_source = _course_source(course_path)
    findings: list[CurriculumFinding] = []
    for warning in course.curriculum_warnings:
        findings.append(
            _finding(
                FindingSeverity.WARNING,
                course_path,
                course_source,
                "deprecated-requirements",
                warning,
                "Move requirements to environment.guest_capabilities.",
            )
        )

    for lesson in course.lessons:
        environment = course.effective_environment(lesson)
        lesson_source = _lesson_source(root, course, lesson.id)
        environment_source = lesson_source if lesson.environment else course_source
        findings.extend(
            _validate_environment(course_path, environment_source, environment)
        )
        for step in lesson.steps:
            objective = any(
                verification.type is not VerificationType.MANUAL_CONFIRMATION
                for verification in step.verifications
            )
            for verification in step.verifications:
                if (
                    verification.type is VerificationType.TEXT_EVIDENCE
                    and verification.matches is not None
                    and _is_broad_yes_no(verification.matches)
                ):
                    findings.append(
                        _warning(
                            course_path,
                            lesson_source,
                            "broad-yes-no-regex",
                            "A yes/no regular expression is not anchored.",
                            "Anchor the complete accepted response with ^ and $ "
                            "or \\A and \\Z.",
                        )
                    )
                elif verification.type is VerificationType.REMOTE_COMMAND:
                    command = verification.command or ""
                    if _UNBOUNDED_COMMAND.search(command):
                        findings.append(
                            _warning(
                                course_path,
                                lesson_source,
                                "interactive-or-unbounded-command",
                                "A remote command appears interactive or unbounded.",
                                "Use a non-interactive command that exits within "
                                "its timeout.",
                            )
                        )
                    findings.extend(
                        _missing_tool_findings(
                            course_path, lesson_source, command, environment
                        )
                    )
                elif (
                    verification.type is VerificationType.PROVIDER_CHECK
                    and verification.check not in known_provider_checks()
                ):
                    findings.append(
                        _warning(
                            course_path,
                            lesson_source,
                            "unknown-provider-check",
                            f"Provider check {verification.check!r} is not built in.",
                            "Use a check returned by known_provider_checks().",
                        )
                    )
                elif (
                    verification.type is VerificationType.MANUAL_CONFIRMATION
                    and objective
                ):
                    findings.append(
                        _warning(
                            course_path,
                            lesson_source,
                            "manual-confirmation-with-objective-check",
                            "Manual confirmation duplicates an objective check "
                            "in this step.",
                            "Remove the redundant attestation or place it in a "
                            "distinct step.",
                        )
                    )
    return findings


def _validate_environment(
    course_path: str, source_path: str, environment: EnvironmentPolicy
) -> list[CurriculumFinding]:
    if environment.scope is EnvironmentScope.NONE:
        return []
    findings: list[CurriculumFinding] = []
    if environment.provider_capability not in _SUPPORTED_PROVIDER_CAPABILITIES:
        findings.append(
            _finding(
                FindingSeverity.ERROR,
                course_path,
                source_path,
                "unsupported-provider-capability",
                f"Provider capability {environment.provider_capability!r} is "
                "unsupported.",
                "Use a provider capability supported by this LearnLab build.",
            )
        )
    if not any(item.startswith("os.") for item in environment.guest_capabilities):
        findings.append(
            _warning(
                course_path,
                source_path,
                "missing-os-capability",
                "A VM environment does not declare an OS guest capability.",
                "Declare the required os.* capability for the effective environment.",
            )
        )
    return findings


def _missing_tool_findings(
    course_path: str,
    source_path: str,
    command: str,
    environment: EnvironmentPolicy,
) -> list[CurriculumFinding]:
    tokens = set(re.findall(r"(?<![-.\w])[a-z][a-z0-9-]*(?![-.\w])", command))
    return [
        _warning(
            course_path,
            source_path,
            "undeclared-tool-capability",
            f"Command uses {tool!r} without declaring {capability!r}.",
            f"Add {capability!r} to the effective guest capabilities.",
        )
        for tool, capability in sorted(_TOOL_COMMANDS.items())
        if tool in tokens and capability not in environment.guest_capabilities
    ]


def _is_broad_yes_no(pattern: str) -> bool:
    lowered = pattern.lower()
    has_yes_no = "yes" in lowered and "no" in lowered and "|" in pattern
    without_flags = re.sub(r"^(?:\(\?[aiLmsux-]+\))*", "", pattern)
    anchored_start = without_flags.startswith("^") or without_flags.startswith(r"\A")
    anchored_end = without_flags.endswith("$") or without_flags.endswith(r"\Z")
    if not (anchored_start and anchored_end):
        return has_yes_no
    start_length = 2 if without_flags.startswith(r"\A") else 1
    end_length = 2 if without_flags.endswith(r"\Z") else 1
    body = without_flags[start_length:-end_length]
    return has_yes_no and _has_top_level_alternation(body)


def _has_top_level_alternation(pattern: str) -> bool:
    depth = 0
    in_character_class = False
    escaped = False
    for character in pattern:
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == "[":
            in_character_class = True
            continue
        if character == "]" and in_character_class:
            in_character_class = False
            continue
        if in_character_class:
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth = max(0, depth - 1)
        elif character == "|" and depth == 0:
            return True
    return False


def _lesson_source(root: Traversable, course: Course, lesson_id: str) -> str:
    relative_base = f"{course.collection_id}/courses/{course.id}/lessons"
    lessons_dir = root / course.collection_id / "courses" / course.id / "lessons"
    try:
        matches = sorted(
            child.name
            for child in lessons_dir.iterdir()
            if child.is_dir() and child.name.endswith(f"-{lesson_id}")
        )
    except OSError:
        matches = []
    directory = matches[0] if matches else lesson_id
    return f"{relative_base}/{directory}/lesson.yaml"


def _course_source(course_path: str) -> str:
    pieces = course_path.split("/")
    if len(pieces) == 2 and all(pieces):
        return f"{pieces[0]}/courses/{pieces[1]}/course.yaml"
    return "."


def _source_from_error(
    error: CurriculumError | CertificationError | OSError,
    root: Traversable,
    default: str,
) -> str:
    if isinstance(error, OSError):
        if not isinstance(error.filename, str):
            return default
        try:
            relative = Path(error.filename).relative_to(Path(str(root)))
        except ValueError:
            return default
        if not relative.parts or ".." in relative.parts:
            return default
        return relative.as_posix()
    message = str(error)
    root_text = str(root).rstrip("/")
    marker = f"{root_text}/"
    if marker not in message:
        return default
    candidate = message.split(marker, 1)[1].split(":", 1)[0]
    return candidate or default


def _relative_message(
    error: CurriculumError | CertificationError | OSError, root: Traversable
) -> str:
    return str(error).replace(f"{str(root).rstrip('/')}/", "")


def _warning(
    course_path: str, source_path: str, code: str, message: str, remedy: str
) -> CurriculumFinding:
    return _finding(
        FindingSeverity.WARNING, course_path, source_path, code, message, remedy
    )


def _finding(
    severity: FindingSeverity,
    course_path: str,
    source_path: str,
    code: str,
    message: str,
    remedy: str,
) -> CurriculumFinding:
    return CurriculumFinding(severity, course_path, source_path, code, message, remedy)


def _finding_key(finding: CurriculumFinding) -> tuple[str, str, str, str]:
    return (
        finding.course_path,
        finding.source_path,
        finding.code,
        finding.message,
    )
