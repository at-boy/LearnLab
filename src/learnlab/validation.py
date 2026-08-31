"""Typed, bounded lesson verification without persistence side effects."""

from __future__ import annotations

import re
from collections.abc import Iterable, Set
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from learnlab.curriculum import MAX_EVIDENCE_BYTES, Verification, VerificationType
from learnlab.providers.base import Provider
from learnlab.ssh import SshCommandTimeout, SshExecutor, SshProfile
from learnlab.state import EnvironmentRecord, StateStore

MAX_SUMMARY_CHARACTERS = 500
_REDACTION_MARKER = "[REDACTED]"


class ValidationPrompt(Protocol):
    """The safe interactive operations validators may request."""

    def ask_text(self, prompt: str) -> str: ...

    def confirm(self, prompt: str) -> bool: ...


@dataclass(frozen=True)
class ValidationContext:
    """Only the dependencies validators may use for one verification."""

    state_store: StateStore | None = None
    profile: SshProfile | None = None
    environment: EnvironmentRecord | None = None
    ssh_executor: SshExecutor | None = None
    provider: Provider | None = None
    prompt: ValidationPrompt | None = None


@dataclass(frozen=True)
class VerificationResult:
    """A safe, bounded verification outcome suitable for later persistence."""

    passed: bool
    summary: str
    validator_type: VerificationType
    self_attested: bool = False
    evidence: str | None = None
    completed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary", self.summary[:MAX_SUMMARY_CHARACTERS])
        if self.evidence is not None:
            object.__setattr__(self, "evidence", _bound_utf8(self.evidence))


class Validator(Protocol):
    """A validator for one curriculum verification declaration."""

    def validate(
        self, context: ValidationContext, verification: Verification
    ) -> VerificationResult: ...


class ValidatorRegistry:
    """Map each declared verification type to exactly one implementation."""

    def __init__(self) -> None:
        self._validators: dict[VerificationType, Validator] = {}

    def register(
        self, verification_type: VerificationType, validator: Validator
    ) -> None:
        verification_type = VerificationType(verification_type)
        if verification_type in self._validators:
            raise ValueError(
                f"Validator already registered for {verification_type.value}"
            )
        self._validators[verification_type] = validator

    def validate(
        self, context: ValidationContext, verification: Verification
    ) -> VerificationResult:
        try:
            validator = self._validators[verification.type]
        except KeyError:
            raise KeyError(
                f"No validator registered for {verification.type.value}"
            ) from None
        return validator.validate(context, verification)


class RemoteCommandValidator:
    """Run only the curriculum-authored command through the strict executor."""

    def validate(
        self, context: ValidationContext, verification: Verification
    ) -> VerificationResult:
        _require_type(verification, VerificationType.REMOTE_COMMAND)
        if (
            context.ssh_executor is None
            or context.profile is None
            or context.environment is None
        ):
            raise ValueError("Remote command validation requires SSH dependencies")
        if verification.command is None or verification.timeout_seconds is None:
            raise ValueError("Remote command verification is incomplete")

        try:
            remote = context.ssh_executor.run(
                context.profile,
                context.environment,
                verification.command,
                verification.timeout_seconds,
            )
        except SshCommandTimeout as error:
            return VerificationResult(
                passed=False,
                summary=verification.failure_message or str(error),
                validator_type=verification.type,
            )

        evidence_parts: list[str] = []
        if remote.exit_code != 0:
            evidence_parts.append(f"exit code: {remote.exit_code}\n")
        if remote.stdout:
            evidence_parts.append(f"stdout:\n{remote.stdout}")
        if remote.stderr:
            evidence_parts.append(f"stderr:\n{remote.stderr}")
        evidence = "".join(evidence_parts) or None
        passed = remote.exit_code == 0
        return VerificationResult(
            passed=passed,
            summary=(
                "Remote command passed"
                if passed
                else verification.failure_message
                or f"Remote command failed with exit code {remote.exit_code}"
            ),
            validator_type=verification.type,
            evidence=evidence,
        )


class TextEvidenceValidator:
    """Compare learner text without interpreting or executing it."""

    def validate(
        self, context: ValidationContext, verification: Verification
    ) -> VerificationResult:
        _require_type(verification, VerificationType.TEXT_EVIDENCE)
        if context.prompt is None:
            raise ValueError("Text evidence validation requires a prompt")
        if verification.prompt is None:
            raise ValueError("Text evidence verification is incomplete")

        raw_evidence = context.prompt.ask_text(verification.prompt)
        if len(raw_evidence.encode("utf-8")) > MAX_EVIDENCE_BYTES:
            return VerificationResult(
                passed=False,
                summary=f"Text evidence must not exceed {MAX_EVIDENCE_BYTES} bytes",
                validator_type=verification.type,
            )
        entered = raw_evidence.strip()

        if verification.equals is not None:
            passed = entered == verification.equals.strip()
        elif verification.matches is not None:
            passed = re.search(verification.matches, entered) is not None
        else:
            raise ValueError("Text evidence verification has no match rule")
        return VerificationResult(
            passed=passed,
            summary=(
                "Text evidence matched"
                if passed
                else verification.failure_message or "Text evidence did not match"
            ),
            validator_type=verification.type,
            evidence=entered,
        )


class ManualConfirmationValidator:
    """Record an explicit learner confirmation as self-attested evidence."""

    def validate(
        self, context: ValidationContext, verification: Verification
    ) -> VerificationResult:
        _require_type(verification, VerificationType.MANUAL_CONFIRMATION)
        if context.prompt is None:
            raise ValueError("Manual confirmation requires a prompt")
        if verification.prompt is None:
            raise ValueError("Manual confirmation verification is incomplete")
        confirmed = context.prompt.confirm(verification.prompt)
        return VerificationResult(
            passed=confirmed,
            summary=(
                "Learner confirmed"
                if confirmed
                else verification.failure_message or "Confirmation incomplete"
            ),
            validator_type=verification.type,
            self_attested=confirmed,
        )


class ProviderCheckValidator:
    """Delegate a named read-only check to the encapsulated provider."""

    def validate(
        self, context: ValidationContext, verification: Verification
    ) -> VerificationResult:
        _require_type(verification, VerificationType.PROVIDER_CHECK)
        if context.provider is None:
            raise ValueError("Provider validation requires a provider")
        if verification.check is None:
            raise ValueError("Provider check verification is incomplete")
        check = context.provider.run_check(verification.check, context.environment)
        return VerificationResult(
            passed=check.ok,
            summary=(
                check.detail
                if check.ok
                else verification.failure_message or check.detail
            ),
            validator_type=verification.type,
            evidence=check.detail,
        )


@dataclass(frozen=True)
class ValidationAttempt:
    """One in-memory validator result paired with its curriculum declaration."""

    verification: Verification
    result: VerificationResult


@dataclass(frozen=True)
class StepValidationResult:
    """Ordered attempts and the next check still requiring completion."""

    attempts: tuple[ValidationAttempt, ...]
    next_incomplete_id: str | None


def validate_step(
    context: ValidationContext,
    verifications: Iterable[Verification],
    registry: ValidatorRegistry,
    *,
    passed_ids: Set[str],
) -> StepValidationResult:
    """Run unpassed checks in order and stop at the first failed result."""
    attempts: list[ValidationAttempt] = []
    for verification in verifications:
        if verification.id in passed_ids:
            continue
        result = registry.validate(context, verification)
        attempts.append(ValidationAttempt(verification, result))
        if not result.passed:
            return StepValidationResult(tuple(attempts), verification.id)
    return StepValidationResult(tuple(attempts), None)


def _require_type(verification: Verification, expected: VerificationType) -> None:
    if verification.type is not expected:
        raise ValueError(f"Expected {expected.value} verification")


def _bound_utf8(value: str) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= MAX_EVIDENCE_BYTES:
        return value
    bounded = encoded[:MAX_EVIDENCE_BYTES].decode("utf-8", errors="ignore")
    marker_start = _partial_redaction_start(bounded)
    if marker_start is None:
        return bounded
    before_marker = bounded[:marker_start]
    while len((before_marker + _REDACTION_MARKER).encode("utf-8")) > MAX_EVIDENCE_BYTES:
        before_marker = before_marker[:-1]
    return before_marker + _REDACTION_MARKER


def _partial_redaction_start(value: str) -> int | None:
    for length in range(len(_REDACTION_MARKER) - 1, 0, -1):
        if value.endswith(_REDACTION_MARKER[:length]):
            return len(value) - length
    return None
