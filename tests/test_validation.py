from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from learnlab.config import ProxmoxProfile
from learnlab.curriculum import Verification, VerificationType
from learnlab.providers.base import Provider, ProviderCheck
from learnlab.ssh import RemoteCommandResult, SshCommandTimeout, SshExecutor
from learnlab.state import EnvironmentPhase, EnvironmentRecord
from learnlab.validation import (
    ManualConfirmationValidator,
    ProviderCheckValidator,
    RemoteCommandValidator,
    TextEvidenceValidator,
    ValidationContext,
    ValidationPrompt,
    Validator,
    ValidatorRegistry,
    VerificationResult,
    validate_step,
)


def make_environment(**overrides: object) -> EnvironmentRecord:
    values: dict[str, object] = {
        "id": "env-1",
        "collection_id": "proxmox",
        "course_id": "proxmox-admin",
        "lesson_id": "api-access",
        "attempt_id": None,
        "profile_name": "home-proxmox",
        "provider_type": "proxmox",
        "phase": EnvironmentPhase.RUNNING,
        "vmid": 102,
        "node": "pve02",
        "ip_address": "192.0.2.10",
    }
    values.update(overrides)
    return EnvironmentRecord(**values)  # type: ignore[arg-type]


class StubPrompt:
    def __init__(self, *, text: str = "", confirmation: bool = False) -> None:
        self._text = text
        self._confirmation = confirmation
        self.requests: list[tuple[str, str]] = []

    def ask_text(self, prompt: str) -> str:
        self.requests.append(("text", prompt))
        return self._text

    def confirm(self, prompt: str) -> bool:
        self.requests.append(("confirm", prompt))
        return self._confirmation


class StubSshExecutor:
    def __init__(
        self,
        result: RemoteCommandResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[str, float]] = []

    def run(
        self,
        profile: ProxmoxProfile,
        environment: EnvironmentRecord,
        command: str,
        timeout: float,
    ) -> RemoteCommandResult:
        self.calls.append((command, timeout))
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


@dataclass
class StubProvider:
    check: ProviderCheck

    def run_check(
        self, check: str, environment: EnvironmentRecord | None
    ) -> ProviderCheck:
        assert check == self.check.name
        return self.check


def context(
    profile: ProxmoxProfile,
    *,
    prompt: ValidationPrompt | None = None,
    ssh_executor: SshExecutor | None = None,
    provider: Provider | None = None,
    environment: EnvironmentRecord | None = None,
) -> ValidationContext:
    return ValidationContext(
        profile=profile,
        environment=environment,
        ssh_executor=ssh_executor,
        provider=provider,
        prompt=prompt,
    )


def test_remote_command_passes_only_for_exit_zero_and_uses_curriculum_command(
    profile_fixture: object,
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    executor = StubSshExecutor(RemoteCommandResult(0, "verified\n", ""))
    verification = Verification(
        id="release",
        type=VerificationType.REMOTE_COMMAND,
        command="grep -q '^ID=nixos' /etc/os-release",
        timeout_seconds=17,
    )

    result = RemoteCommandValidator().validate(
        context(
            profile,
            ssh_executor=cast(SshExecutor, executor),
            environment=make_environment(),
        ),
        verification,
    )

    assert result.passed is True
    assert result.validator_type is VerificationType.REMOTE_COMMAND
    assert result.evidence == "stdout:\nverified\n"
    assert executor.calls == [("grep -q '^ID=nixos' /etc/os-release", 17)]


def test_remote_command_failure_returns_bounded_safe_output(
    profile_fixture: object,
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    executor = StubSshExecutor(
        RemoteCommandResult(23, "safe stdout\n" + "x" * 9000, "safe stderr\n")
    )
    verification = Verification(
        id="release",
        type=VerificationType.REMOTE_COMMAND,
        failure_message="The release check failed",
        command="false",
        timeout_seconds=30,
    )

    result = RemoteCommandValidator().validate(
        context(
            profile,
            ssh_executor=cast(SshExecutor, executor),
            environment=make_environment(),
        ),
        verification,
    )

    assert result.passed is False
    assert result.summary == "The release check failed"
    assert result.evidence is not None
    assert result.evidence.startswith("exit code: 23\nstdout:\nsafe stdout")
    assert len(result.evidence.encode("utf-8")) <= 8 * 1024


def test_remote_timeout_is_a_failed_result_without_command_disclosure(
    profile_fixture: object,
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    executor = StubSshExecutor(error=SshCommandTimeout("timed out after 9 seconds"))
    command = "test private-value = private-value"
    verification = Verification(
        id="release",
        type=VerificationType.REMOTE_COMMAND,
        command=command,
        timeout_seconds=9,
    )

    result = RemoteCommandValidator().validate(
        context(
            profile,
            ssh_executor=cast(SshExecutor, executor),
            environment=make_environment(),
        ),
        verification,
    )

    assert result.passed is False
    assert "timed out" in result.summary
    assert command not in result.summary
    assert result.evidence is None


@pytest.mark.parametrize(
    ("entered", "expected", "passed"),
    [("  nixos  \n", "nixos", True), ("nix os", "nixos", False)],
)
def test_text_exact_comparison_trims_only_outer_whitespace(
    profile_fixture: object, entered: str, expected: str, passed: bool
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    prompt = StubPrompt(text=entered)
    verification = Verification(
        id="release-text",
        type=VerificationType.TEXT_EVIDENCE,
        prompt="Paste the release ID",
        equals=expected,
    )

    result = TextEvidenceValidator().validate(
        context(profile, prompt=prompt), verification
    )

    assert result.passed is passed
    assert result.evidence == entered.strip()
    assert prompt.requests == [("text", "Paste the release ID")]


def test_text_regex_searches_the_submitted_bounded_evidence(
    profile_fixture: object,
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    prompt = StubPrompt(text="release=NixOS 26.05; status=ready")
    verification = Verification(
        id="release-text",
        type=VerificationType.TEXT_EVIDENCE,
        prompt="Paste the release line",
        matches=r"NixOS\s+26\.05",
    )

    result = TextEvidenceValidator().validate(
        context(profile, prompt=prompt), verification
    )

    assert result.passed is True
    assert result.evidence == "release=NixOS 26.05; status=ready"


def test_oversized_text_is_rejected_without_returning_persistable_evidence(
    profile_fixture: object,
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    prompt = StubPrompt(text="x" * (8 * 1024 + 1))
    verification = Verification(
        id="release-text",
        type=VerificationType.TEXT_EVIDENCE,
        prompt="Paste evidence",
        matches="x+",
    )

    result = TextEvidenceValidator().validate(
        context(profile, prompt=prompt), verification
    )

    assert result.passed is False
    assert result.evidence is None
    assert "8192 bytes" in result.summary


def test_outer_whitespace_cannot_hide_oversized_text_evidence(
    profile_fixture: object,
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    prompt = StubPrompt(text=" " * (8 * 1024 + 1) + "ready")
    verification = Verification(
        id="release-text",
        type=VerificationType.TEXT_EVIDENCE,
        prompt="Paste evidence",
        equals="ready",
    )

    result = TextEvidenceValidator().validate(
        context(profile, prompt=prompt), verification
    )

    assert result.passed is False
    assert result.evidence is None
    assert "8192 bytes" in result.summary


@pytest.mark.parametrize(("answer", "passed"), [(True, True), (False, False)])
def test_manual_confirmation_is_self_attested_only_when_confirmed(
    profile_fixture: object, answer: bool, passed: bool
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    prompt = StubPrompt(confirmation=answer)
    verification = Verification(
        id="reviewed",
        type=VerificationType.MANUAL_CONFIRMATION,
        prompt="Have you reviewed the output?",
    )

    result = ManualConfirmationValidator().validate(
        context(profile, prompt=prompt), verification
    )

    assert result.passed is passed
    assert result.self_attested is answer
    assert prompt.requests == [("confirm", "Have you reviewed the output?")]


def test_provider_validator_maps_named_check_to_safe_result(
    profile_fixture: object,
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    provider = StubProvider(ProviderCheck("vm-running", False, "VM 102 is stopped"))
    verification = Verification(
        id="running",
        type=VerificationType.PROVIDER_CHECK,
        failure_message="Start the environment before continuing",
        check="vm-running",
    )

    result = ProviderCheckValidator().validate(
        context(
            profile,
            provider=cast(Provider, provider),
            environment=make_environment(),
        ),
        verification,
    )

    assert result.passed is False
    assert result.summary == "Start the environment before continuing"
    assert result.evidence == "VM 102 is stopped"


def test_result_bounds_summary_by_characters_and_evidence_by_bytes() -> None:
    result = VerificationResult(
        passed=False,
        summary="s" * 600,
        validator_type=VerificationType.TEXT_EVIDENCE,
        evidence="🙂" * 3000,
    )

    assert result.summary == "s" * 500
    assert result.evidence is not None
    assert len(result.evidence.encode("utf-8")) <= 8 * 1024


def test_result_truncation_preserves_complete_redaction_markers() -> None:
    result = VerificationResult(
        passed=False,
        summary="failed",
        validator_type=VerificationType.REMOTE_COMMAND,
        evidence="x" * 8188 + "[REDACTED]",
    )

    assert result.evidence is not None
    assert result.evidence.endswith("[REDACTED]")
    assert len(result.evidence.encode("utf-8")) <= 8 * 1024


class FixedValidator:
    def __init__(self, passed: bool, calls: list[str]) -> None:
        self._passed = passed
        self._calls = calls

    def validate(
        self, context: ValidationContext, verification: Verification
    ) -> VerificationResult:
        self._calls.append(verification.id)
        return VerificationResult(
            passed=self._passed,
            summary="passed" if self._passed else "failed",
            validator_type=verification.type,
        )


def test_registry_rejects_duplicate_and_unknown_validator_types(
    profile_fixture: object,
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    registry = ValidatorRegistry()
    validator = cast(Validator, FixedValidator(True, []))
    registry.register(VerificationType.REMOTE_COMMAND, validator)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(VerificationType.REMOTE_COMMAND, validator)
    with pytest.raises(KeyError, match="text-evidence"):
        registry.validate(
            context(profile),
            Verification("text", VerificationType.TEXT_EVIDENCE),
        )


def test_validate_step_runs_ordered_unpassed_items_and_stops_on_first_failure(
    profile_fixture: object,
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    calls: list[str] = []
    registry = ValidatorRegistry()
    registry.register(
        VerificationType.REMOTE_COMMAND,
        cast(Validator, FixedValidator(True, calls)),
    )
    registry.register(
        VerificationType.TEXT_EVIDENCE,
        cast(Validator, FixedValidator(False, calls)),
    )
    registry.register(
        VerificationType.MANUAL_CONFIRMATION,
        cast(Validator, FixedValidator(True, calls)),
    )
    verifications = (
        Verification("already-done", VerificationType.REMOTE_COMMAND),
        Verification("passes-now", VerificationType.REMOTE_COMMAND),
        Verification("fails-now", VerificationType.TEXT_EVIDENCE),
        Verification("not-run", VerificationType.MANUAL_CONFIRMATION),
    )

    outcome = validate_step(
        context(profile),
        verifications,
        registry,
        passed_ids={"already-done"},
    )

    assert calls == ["passes-now", "fails-now"]
    assert [attempt.verification.id for attempt in outcome.attempts] == [
        "passes-now",
        "fails-now",
    ]
    assert outcome.next_incomplete_id == "fails-now"


def test_validate_step_returns_none_after_all_required_items_pass(
    profile_fixture: object,
) -> None:
    profile = cast(ProxmoxProfile, profile_fixture())  # type: ignore[operator]
    calls: list[str] = []
    registry = ValidatorRegistry()
    registry.register(
        VerificationType.REMOTE_COMMAND,
        cast(Validator, FixedValidator(True, calls)),
    )
    verifications = (
        Verification("first", VerificationType.REMOTE_COMMAND),
        Verification("second", VerificationType.REMOTE_COMMAND),
    )

    outcome = validate_step(context(profile), verifications, registry, passed_ids=set())

    assert calls == ["first", "second"]
    assert outcome.next_incomplete_id is None
