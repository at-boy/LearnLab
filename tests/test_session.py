from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from learnlab.curriculum import (
    Course,
    EnvironmentPolicy,
    EnvironmentScope,
    Lesson,
    Step,
    Verification,
    VerificationType,
)
from learnlab.errors import ProviderError
from learnlab.lifecycle import EnvironmentResolution, LifecycleService, StartRequest
from learnlab.session import CourseSession, SessionAction, SessionOutcome
from learnlab.state import (
    CompletionSource,
    EnvironmentPhase,
    EnvironmentRecord,
    ProgressStatus,
    StateStore,
    StepStatus,
    VerificationStatus,
)
from learnlab.validation import ValidationContext, VerificationResult

COURSE_PATH = ("demo", "operations")


def verification(check_id: str) -> Verification:
    return Verification(
        id=check_id,
        type=VerificationType.MANUAL_CONFIRMATION,
        prompt=f"Confirm {check_id}",
    )


def course_with_steps(*steps: Step) -> Course:
    lesson = Lesson(id="basics", title="Basics", steps=tuple(steps))
    return Course(
        collection_id=COURSE_PATH[0],
        id=COURSE_PATH[1],
        title="Operations",
        lessons=(lesson,),
        environment=EnvironmentPolicy(EnvironmentScope.NONE),
    )


@dataclass
class NoEnvironmentLifecycle:
    calls: int = 0

    def ensure_environment(
        self,
        request: StartRequest,
        policy: EnvironmentPolicy,
        replace_confirmed: bool = False,
    ) -> EnvironmentResolution:
        self.calls += 1
        return EnvironmentResolution("none")


class RecordingPrompt:
    def __init__(self, store: StateStore, step_path: tuple[str, str, str, str]) -> None:
        self.store = store
        self.step_path = step_path
        self.presented: list[str] = []
        self.completed_with_persisted_pass = False

    def present_lesson(self, course: Course, lesson: Lesson) -> None:
        return None

    def present_step(
        self, lesson: Lesson, step: Step, position: int, total: int
    ) -> None:
        return None

    def begin_verification(
        self,
        lesson: Lesson,
        step: Step,
        check: Verification,
        position: int,
        total: int,
    ) -> SessionAction:
        self.presented.append(check.id)
        cursor = self.store.session_cursor(COURSE_PATH)
        assert cursor is not None
        assert (cursor.lesson_id, cursor.step_id, cursor.verification_id) == (
            lesson.id,
            step.id,
            check.id,
        )
        return SessionAction.READY

    def present_result(self, check: Verification, result: VerificationResult) -> None:
        cursor = self.store.session_cursor(COURSE_PATH)
        assert cursor is not None
        assert cursor.verification_id == check.id
        records = {
            record.verification_id: record
            for record in self.store.verification_records(self.step_path)
        }
        assert records[check.id].status is (
            VerificationStatus.PASSED if result.passed else VerificationStatus.FAILED
        )

    def failed_verification(
        self, check: Verification, result: VerificationResult
    ) -> SessionAction:
        raise AssertionError("passing resumed verification must not ask to retry")

    def lesson_completed(
        self, course: Course, lesson: Lesson, next_lesson: Lesson | None
    ) -> SessionAction:
        records = self.store.verification_records(self.step_path)
        self.completed_with_persisted_pass = {
            record.verification_id: record.status for record in records
        } == {
            "already-passed": VerificationStatus.PASSED,
            "resume-here": VerificationStatus.PASSED,
        }
        return SessionAction.EXIT

    def choose_review_lesson(self, course: Course) -> str | None:
        raise AssertionError("review was not requested")

    def confirm_environment_change(
        self, resolution: EnvironmentResolution, lesson: Lesson
    ) -> bool:
        raise AssertionError("none-scoped lesson must not ask about environments")

    def legacy_completion(self, lesson: Lesson) -> None:
        return None

    def ask_text(self, prompt: str) -> str:
        raise AssertionError("manual validator fake does not ask for text")

    def confirm(self, prompt: str) -> bool:
        raise AssertionError("scripted validator handles confirmation")


class PassingRegistry:
    def validate(
        self, context: ValidationContext, check: Verification
    ) -> VerificationResult:
        return VerificationResult(
            passed=True,
            summary="passed",
            validator_type=check.type,
            self_attested=True,
        )


class ScriptedRegistry:
    def __init__(self, results: dict[str, list[bool]]) -> None:
        self.results = results
        self.calls: list[str] = []

    def validate(
        self, context: ValidationContext, check: Verification
    ) -> VerificationResult:
        self.calls.append(check.id)
        passed = self.results[check.id].pop(0)
        return VerificationResult(
            passed=passed,
            summary="safe pass" if passed else "safe retry guidance",
            validator_type=check.type,
            self_attested=passed,
        )


class FailingRegistry:
    def validate(
        self, context: ValidationContext, check: Verification
    ) -> VerificationResult:
        raise ProviderError("SSH failed with token-secret")


class UnsafeResultRegistry:
    def validate(
        self, context: ValidationContext, check: Verification
    ) -> VerificationResult:
        return VerificationResult(
            passed=False,
            summary="q" * 500,
            validator_type=check.type,
            evidence="q" * (8 * 1024),
            completed_at="token-secret" * 10_000,
        )


class RetryingPrompt(RecordingPrompt):
    def __init__(self, store: StateStore, step_path: tuple[str, str, str, str]) -> None:
        super().__init__(store, step_path)
        self.failures: list[str] = []

    def failed_verification(
        self, check: Verification, result: VerificationResult
    ) -> SessionAction:
        self.failures.append(result.summary)
        return SessionAction.RETRY


class SaveAfterFailurePrompt(RetryingPrompt):
    def failed_verification(
        self, check: Verification, result: VerificationResult
    ) -> SessionAction:
        self.failures.append(result.summary)
        return SessionAction.SAVE_AND_EXIT


@dataclass(frozen=True)
class FakeProfile:
    name: str = "lab"
    node: str = "node-a"
    ssh_user: str = "student"
    ssh_identity_file: Path = Path("learnlab-test-key")


class ReusingLifecycle:
    def __init__(self) -> None:
        self.calls: list[tuple[str, EnvironmentScope, bool]] = []

    def ensure_environment(
        self,
        request: StartRequest,
        policy: EnvironmentPolicy,
        replace_confirmed: bool = False,
    ) -> EnvironmentResolution:
        lesson_id = request.lesson.id
        self.calls.append((lesson_id, policy.scope, replace_confirmed))
        status = "created" if len(self.calls) == 1 else "reused"
        return EnvironmentResolution(status)


class ReplacingLifecycle:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def ensure_environment(
        self,
        request: StartRequest,
        policy: EnvironmentPolicy,
        replace_confirmed: bool = False,
    ) -> EnvironmentResolution:
        lesson_id = request.lesson.id
        self.calls.append((lesson_id, replace_confirmed))
        if lesson_id == "second" and not replace_confirmed:
            return EnvironmentResolution("replacement_required")
        return EnvironmentResolution("created")


class NavigationPrompt:
    def __init__(self, lesson_actions: dict[str, SessionAction]) -> None:
        self.lesson_actions = lesson_actions
        self.presented_lessons: list[str] = []
        self.presented_steps: list[str] = []

    def present_lesson(self, course: Course, lesson: Lesson) -> None:
        self.presented_lessons.append(lesson.id)

    def present_step(
        self, lesson: Lesson, step: Step, position: int, total: int
    ) -> None:
        self.presented_steps.append(step.id)

    def begin_verification(
        self,
        lesson: Lesson,
        step: Step,
        check: Verification,
        position: int,
        total: int,
    ) -> SessionAction:
        return SessionAction.READY

    def present_result(self, check: Verification, result: VerificationResult) -> None:
        return None

    def failed_verification(
        self, check: Verification, result: VerificationResult
    ) -> SessionAction:
        raise AssertionError("navigation checks are scripted to pass")

    def lesson_completed(
        self, course: Course, lesson: Lesson, next_lesson: Lesson | None
    ) -> SessionAction:
        return self.lesson_actions[lesson.id]

    def choose_review_lesson(self, course: Course) -> str | None:
        raise AssertionError("review was not requested")

    def confirm_environment_change(
        self, resolution: EnvironmentResolution, lesson: Lesson
    ) -> bool:
        raise AssertionError("course-scoped environment must be reusable")

    def legacy_completion(self, lesson: Lesson) -> None:
        return None

    def ask_text(self, prompt: str) -> str:
        raise AssertionError("scripted validator does not ask for text")

    def confirm(self, prompt: str) -> bool:
        raise AssertionError("scripted validator handles confirmation")


class ReplacementPrompt(NavigationPrompt):
    def __init__(self, lesson_actions: dict[str, SessionAction]) -> None:
        super().__init__(lesson_actions)
        self.environment_changes: list[str] = []

    def confirm_environment_change(
        self, resolution: EnvironmentResolution, lesson: Lesson
    ) -> bool:
        self.environment_changes.append(lesson.id)
        return True


class InterruptingPrompt(NavigationPrompt):
    def begin_verification(
        self,
        lesson: Lesson,
        step: Step,
        check: Verification,
        position: int,
        total: int,
    ) -> SessionAction:
        raise KeyboardInterrupt


class LegacyPrompt(NavigationPrompt):
    def __init__(self, lesson_actions: dict[str, SessionAction]) -> None:
        super().__init__(lesson_actions)
        self.legacy_labels: list[str] = []

    def legacy_completion(self, lesson: Lesson) -> None:
        self.legacy_labels.append(lesson.id)


class SavingPrompt(NavigationPrompt):
    def begin_verification(
        self,
        lesson: Lesson,
        step: Step,
        check: Verification,
        position: int,
        total: int,
    ) -> SessionAction:
        return SessionAction.SAVE_AND_EXIT


class ProviderAccessForbidden:
    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"none scope accessed provider attribute {name}")


class LifecycleAccessForbidden:
    def __init__(self) -> None:
        self.called = False

    def ensure_environment(
        self,
        request: StartRequest,
        policy: EnvironmentPolicy,
        replace_confirmed: bool = False,
    ) -> EnvironmentResolution:
        self.called = True
        raise AssertionError("lifecycle accessed without a provider profile")


class CancellingReplacementPrompt(NavigationPrompt):
    def confirm_environment_change(
        self, resolution: EnvironmentResolution, lesson: Lesson
    ) -> bool:
        return False


class ReviewPrompt(LegacyPrompt):
    def choose_review_lesson(self, course: Course) -> str | None:
        return "legacy"


class ResultCapturingPrompt(NavigationPrompt):
    def __init__(self) -> None:
        super().__init__({})
        self.results: list[VerificationResult] = []

    def present_result(self, check: Verification, result: VerificationResult) -> None:
        self.results.append(result)

    def failed_verification(
        self, check: Verification, result: VerificationResult
    ) -> SessionAction:
        self.results.append(result)
        return SessionAction.SAVE_AND_EXIT


class ValidatedReviewFailurePrompt(NavigationPrompt):
    def __init__(self) -> None:
        super().__init__({"reviewed": SessionAction.EXIT})
        self.presented_checks: list[str] = []

    def begin_verification(
        self,
        lesson: Lesson,
        step: Step,
        check: Verification,
        position: int,
        total: int,
    ) -> SessionAction:
        self.presented_checks.append(check.id)
        return SessionAction.READY

    def failed_verification(
        self, check: Verification, result: VerificationResult
    ) -> SessionAction:
        return SessionAction.SAVE_AND_EXIT


class ValidatedReviewInterruptPrompt(ValidatedReviewFailurePrompt):
    def begin_verification(
        self,
        lesson: Lesson,
        step: Step,
        check: Verification,
        position: int,
        total: int,
    ) -> SessionAction:
        self.presented_checks.append(check.id)
        raise KeyboardInterrupt


class ValidatedMenuReviewPrompt(NavigationPrompt):
    def __init__(self) -> None:
        super().__init__(
            {"current": SessionAction.REVIEW, "reviewed": SessionAction.EXIT}
        )
        self.presented_checks: list[tuple[str, str]] = []

    def begin_verification(
        self,
        lesson: Lesson,
        step: Step,
        check: Verification,
        position: int,
        total: int,
    ) -> SessionAction:
        self.presented_checks.append((lesson.id, check.id))
        return SessionAction.READY

    def choose_review_lesson(self, course: Course) -> str | None:
        return "reviewed"


def mark_legacy_complete(store: StateStore, lesson_id: str) -> None:
    store.mark_lesson(*COURSE_PATH, lesson_id, ProgressStatus.COMPLETED)
    connection = sqlite3.connect(store.db_path)
    try:
        connection.execute(
            "UPDATE progress SET completion_source = ? "
            "WHERE collection_id = ? AND course_id = ? AND lesson_id = ?",
            (CompletionSource.LEGACY.value, *COURSE_PATH, lesson_id),
        )
        connection.commit()
    finally:
        connection.close()


def mark_validated_complete(store: StateStore, lesson: Lesson) -> None:
    lesson_path = (*COURSE_PATH, lesson.id)
    for step in lesson.steps:
        step_path = (*lesson_path, step.id)
        store.start_step(step_path)
        for check in step.verifications:
            store.record_verification_result(
                step_path,
                check.id,
                passed=True,
                evidence="original safe evidence",
                validator_type=check.type,
                self_attested=True,
            )
        store.complete_step(step_path, tuple(check.id for check in step.verifications))
    store.complete_lesson_validated(
        lesson_path, tuple(step.id for step in lesson.steps)
    )


def test_resume_skips_passed_check_and_persists_next_result_before_advancing(
    tmp_path: Path,
) -> None:
    checks = (verification("already-passed"), verification("resume-here"))
    course = course_with_steps(
        Step(
            id="inspect",
            title="Inspect",
            instructions="Inspect the system.",
            verifications=checks,
        )
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    step_path = (*COURSE_PATH, "basics", "inspect")
    store.start_step(step_path)
    store.record_verification_result(
        step_path,
        "already-passed",
        passed=True,
        evidence="first result",
        validator_type=VerificationType.MANUAL_CONFIRMATION,
        self_attested=True,
    )
    store.record_verification_result(
        step_path,
        "resume-here",
        passed=False,
        evidence=None,
        validator_type=VerificationType.MANUAL_CONFIRMATION,
    )
    prompt = RecordingPrompt(store, step_path)

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=PassingRegistry(),
        prompt=prompt,
    ).run()

    assert prompt.presented == ["resume-here"]
    assert prompt.completed_with_persisted_pass is True
    records = {
        record.verification_id: record
        for record in store.verification_records(step_path)
    }
    assert records["already-passed"].attempt_count == 1
    assert records["resume-here"].attempt_count == 2
    assert outcome.action is SessionAction.EXIT


def test_failed_check_retries_without_repeating_passed_checks_and_completes_step(
    tmp_path: Path,
) -> None:
    checks = (verification("first"), verification("retry-me"))
    course = course_with_steps(
        Step(
            id="inspect",
            title="Inspect",
            instructions="Inspect the system.",
            verifications=checks,
        )
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    step_path = (*COURSE_PATH, "basics", "inspect")
    prompt = RetryingPrompt(store, step_path)
    registry = ScriptedRegistry({"first": [True], "retry-me": [False, True]})

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=registry,
        prompt=prompt,
    ).run()

    assert registry.calls == ["first", "retry-me", "retry-me"]
    assert prompt.presented == ["first", "retry-me"]
    assert prompt.failures == ["safe retry guidance"]
    records = {
        record.verification_id: record
        for record in store.verification_records(step_path)
    }
    assert records["first"].attempt_count == 1
    assert records["retry-me"].attempt_count == 2
    assert (
        store.step_statuses((*COURSE_PATH, "basics"))["inspect"] is StepStatus.COMPLETED
    )
    assert outcome.lesson_completed is True


def test_failed_check_can_save_with_failed_result_and_cursor_persisted(
    tmp_path: Path,
) -> None:
    course = course_with_steps(
        Step(
            id="inspect",
            title="Inspect",
            instructions="Inspect the system.",
            verifications=(verification("save-here"),),
        )
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    step_path = (*COURSE_PATH, "basics", "inspect")
    prompt = SaveAfterFailurePrompt(store, step_path)

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=ScriptedRegistry({"save-here": [False]}),
        prompt=prompt,
    ).run()

    [record] = store.verification_records(step_path)
    cursor = store.session_cursor(COURSE_PATH)
    assert record.status is VerificationStatus.FAILED
    assert record.attempt_count == 1
    assert cursor is not None
    assert cursor.verification_id == "save-here"
    assert (
        store.step_statuses((*COURSE_PATH, "basics"))["inspect"]
        is StepStatus.IN_PROGRESS
    )
    assert store.lesson_completion_source((*COURSE_PATH, "basics")) is None
    assert outcome.action is SessionAction.SAVE_AND_EXIT


def test_all_required_checks_complete_each_step_before_lesson_completion(
    tmp_path: Path,
) -> None:
    course = course_with_steps(
        Step(
            id="first-step",
            title="First",
            instructions="Complete the first step.",
            verifications=(verification("first-check"),),
        ),
        Step(
            id="second-step",
            title="Second",
            instructions="Complete the second step.",
            verifications=(verification("second-check"),),
        ),
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    prompt = NavigationPrompt({"basics": SessionAction.EXIT})

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=ScriptedRegistry({"first-check": [True], "second-check": [True]}),
        prompt=prompt,
    ).run()

    assert prompt.presented_steps == ["first-step", "second-step"]
    assert store.step_statuses((*COURSE_PATH, "basics")) == {
        "first-step": StepStatus.COMPLETED,
        "second-step": StepStatus.COMPLETED,
    }
    assert (
        store.lesson_completion_source((*COURSE_PATH, "basics"))
        is CompletionSource.VALIDATED
    )
    assert outcome.lesson_completed is True


def test_continue_chooses_first_incomplete_lesson_and_reuses_course_scope(
    tmp_path: Path,
) -> None:
    lessons = tuple(
        Lesson(
            id=lesson_id,
            title=lesson_id.title(),
            steps=(
                Step(
                    id="do-work",
                    title="Do work",
                    instructions="Complete the work.",
                    verifications=(verification("confirm-work"),),
                ),
            ),
        )
        for lesson_id in ("first", "already-complete", "third")
    )
    course = Course(
        collection_id=COURSE_PATH[0],
        id=COURSE_PATH[1],
        title="Operations",
        lessons=lessons,
        environment=EnvironmentPolicy(EnvironmentScope.COURSE, "demo.vm"),
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    store.complete_lesson(
        *COURSE_PATH,
        "already-complete",
        source=CompletionSource.MANUAL_OVERRIDE,
    )
    lifecycle = ReusingLifecycle()
    prompt = NavigationPrompt(
        {"first": SessionAction.CONTINUE, "third": SessionAction.EXIT}
    )
    registry = ScriptedRegistry({"confirm-work": [True, True]})

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=lifecycle,
        validators=registry,
        prompt=prompt,
        profile=FakeProfile(),
        provider_type="fake",
    ).run()

    assert prompt.presented_lessons == ["first", "third"]
    assert lifecycle.calls == [
        ("first", EnvironmentScope.COURSE, False),
        ("third", EnvironmentScope.COURSE, False),
    ]
    assert store.completed_lessons(*COURSE_PATH) == {
        "first",
        "already-complete",
        "third",
    }
    assert outcome.course_completed is True


def test_lesson_scope_confirms_replacement_before_resolving_next_lesson(
    tmp_path: Path,
) -> None:
    lessons = tuple(
        Lesson(
            id=lesson_id,
            title=lesson_id.title(),
            steps=(
                Step(
                    id="do-work",
                    title="Do work",
                    instructions="Complete the work.",
                    verifications=(verification("confirm-work"),),
                ),
            ),
        )
        for lesson_id in ("first", "second")
    )
    course = Course(
        collection_id=COURSE_PATH[0],
        id=COURSE_PATH[1],
        title="Operations",
        lessons=lessons,
        environment=EnvironmentPolicy(EnvironmentScope.LESSON, "demo.vm"),
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    lifecycle = ReplacingLifecycle()
    prompt = ReplacementPrompt(
        {"first": SessionAction.CONTINUE, "second": SessionAction.EXIT}
    )

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=lifecycle,
        validators=ScriptedRegistry({"confirm-work": [True, True]}),
        prompt=prompt,
        profile=FakeProfile(),
        provider_type="fake",
    ).run()

    assert lifecycle.calls == [
        ("first", False),
        ("second", False),
        ("second", True),
    ]
    assert prompt.environment_changes == ["second"]
    assert outcome.course_completed is True


def test_interrupt_returns_saved_outcome_with_current_cursor(tmp_path: Path) -> None:
    check = verification("resume-check")
    course = course_with_steps(
        Step(
            id="inspect",
            title="Inspect",
            instructions="Inspect the system.",
            verifications=(check,),
        )
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=ScriptedRegistry({"resume-check": [True]}),
        prompt=InterruptingPrompt({}),
    ).run()

    cursor = store.session_cursor(COURSE_PATH)
    assert cursor is not None
    assert (cursor.lesson_id, cursor.step_id, cursor.verification_id) == (
        "basics",
        "inspect",
        "resume-check",
    )
    assert (
        store.step_statuses((*COURSE_PATH, "basics"))["inspect"]
        is StepStatus.IN_PROGRESS
    )
    assert store.verification_records((*COURSE_PATH, "basics", "inspect")) == []
    assert outcome == SessionOutcome(
        SessionAction.SAVE_AND_EXIT,
        "basics",
    )


def test_legacy_completion_is_labeled_and_skipped_unless_reviewed(
    tmp_path: Path,
) -> None:
    lessons = tuple(
        Lesson(
            id=lesson_id,
            title=lesson_id.title(),
            steps=(
                Step(
                    id="do-work",
                    title="Do work",
                    instructions="Complete the work.",
                    verifications=(verification("confirm-work"),),
                ),
            ),
        )
        for lesson_id in ("legacy", "current")
    )
    course = Course(
        collection_id=COURSE_PATH[0],
        id=COURSE_PATH[1],
        title="Operations",
        lessons=lessons,
        environment=EnvironmentPolicy(EnvironmentScope.NONE),
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    mark_legacy_complete(store, "legacy")
    prompt = LegacyPrompt({"current": SessionAction.EXIT})

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=ScriptedRegistry({"confirm-work": [True]}),
        prompt=prompt,
    ).run(lesson_id="legacy")

    assert prompt.legacy_labels == ["legacy"]
    assert prompt.presented_lessons == ["current"]
    assert outcome.lesson_id == "current"


def test_explicit_legacy_review_runs_verifications_and_replaces_provenance(
    tmp_path: Path,
) -> None:
    lesson = Lesson(
        id="legacy",
        title="Legacy",
        steps=(
            Step(
                id="do-work",
                title="Do work",
                instructions="Complete the work.",
                verifications=(verification("confirm-work"),),
            ),
        ),
    )
    course = Course(
        collection_id=COURSE_PATH[0],
        id=COURSE_PATH[1],
        title="Operations",
        lessons=(lesson,),
        environment=EnvironmentPolicy(EnvironmentScope.NONE),
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    mark_legacy_complete(store, "legacy")
    prompt = LegacyPrompt({"legacy": SessionAction.EXIT})

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=ScriptedRegistry({"confirm-work": [True]}),
        prompt=prompt,
    ).run(lesson_id="legacy", review_completed=True)

    assert prompt.legacy_labels == ["legacy"]
    assert prompt.presented_lessons == ["legacy"]
    assert (
        store.lesson_completion_source((*COURSE_PATH, "legacy"))
        is CompletionSource.VALIDATED
    )
    assert outcome.lesson_completed is True


def test_validation_failure_returns_redacted_full_curriculum_context(
    tmp_path: Path,
) -> None:
    course = course_with_steps(
        Step(
            id="inspect",
            title="Inspect",
            instructions="Inspect the system.",
            verifications=(verification("contextual-check"),),
        )
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=FailingRegistry(),
        prompt=NavigationPrompt({}),
        secrets={"token-secret"},
    ).run()

    assert outcome.action is SessionAction.ERROR
    assert outcome.error is not None
    assert "course demo/operations" in outcome.error
    assert "lesson basics" in outcome.error
    assert "step inspect" in outcome.error
    assert "check contextual-check" in outcome.error
    assert "token-secret" not in outcome.error
    assert "[REDACTED]" in outcome.error


def test_failed_result_is_redacted_and_rebounded_before_persistence_and_prompts(
    tmp_path: Path,
) -> None:
    course = course_with_steps(
        Step(
            id="inspect",
            title="Inspect",
            instructions="Inspect the system.",
            verifications=(verification("safe-result"),),
        )
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    prompt = ResultCapturingPrompt()

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=UnsafeResultRegistry(),
        prompt=prompt,
        secrets={"q", "token-secret"},
    ).run()

    [record] = store.verification_records((*COURSE_PATH, "basics", "inspect"))
    assert record.evidence is not None
    assert "q" not in record.evidence
    assert "[REDACTED]" in record.evidence
    assert len(record.evidence.encode("utf-8")) <= 8 * 1024
    assert len(prompt.results) == 2
    assert prompt.results[0] is prompt.results[1]
    for result in prompt.results:
        assert "q" not in result.summary
        assert "[REDACTED]" in result.summary
        assert len(result.summary) <= 500
        assert result.evidence == record.evidence
        assert "token-secret" not in result.completed_at
        assert len(result.completed_at) <= 40
        parsed_result_time = datetime.fromisoformat(result.completed_at)
        assert parsed_result_time.tzinfo is UTC
    assert record.attempted_at is not None
    assert record.completed_at is None
    parsed_attempted_time = datetime.fromisoformat(record.attempted_at)
    assert parsed_attempted_time.tzinfo is UTC
    assert "q" not in repr(outcome)
    assert outcome.action is SessionAction.SAVE_AND_EXIT


def test_failed_validated_review_reruns_check_without_clearing_prior_success(
    tmp_path: Path,
) -> None:
    reviewed = Lesson(
        id="reviewed",
        title="Reviewed",
        steps=(
            Step(
                id="do-work",
                title="Do work",
                instructions="Complete the work.",
                verifications=(verification("review-check"),),
            ),
        ),
    )
    course = Course(
        collection_id=COURSE_PATH[0],
        id=COURSE_PATH[1],
        title="Operations",
        lessons=(reviewed,),
        environment=EnvironmentPolicy(EnvironmentScope.NONE),
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    mark_validated_complete(store, reviewed)
    prompt = ValidatedReviewFailurePrompt()

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=ScriptedRegistry({"review-check": [False]}),
        prompt=prompt,
    ).run(lesson_id="reviewed", review_completed=True)

    [record] = store.verification_records((*COURSE_PATH, "reviewed", "do-work"))
    assert prompt.presented_steps == ["do-work"]
    assert prompt.presented_checks == ["review-check"]
    assert record.status is VerificationStatus.PASSED
    assert record.attempt_count == 2
    assert record.evidence == "original safe evidence"
    assert (
        store.step_statuses((*COURSE_PATH, "reviewed"))["do-work"]
        is StepStatus.COMPLETED
    )
    assert (
        store.lesson_completion_source((*COURSE_PATH, "reviewed"))
        is CompletionSource.VALIDATED
    )
    assert outcome.action is SessionAction.SAVE_AND_EXIT


def test_interrupted_validated_review_preserves_prior_completion_and_result(
    tmp_path: Path,
) -> None:
    reviewed = Lesson(
        id="reviewed",
        title="Reviewed",
        steps=(
            Step(
                id="do-work",
                title="Do work",
                instructions="Complete the work.",
                verifications=(verification("review-check"),),
            ),
        ),
    )
    course = Course(
        collection_id=COURSE_PATH[0],
        id=COURSE_PATH[1],
        title="Operations",
        lessons=(reviewed,),
        environment=EnvironmentPolicy(EnvironmentScope.NONE),
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    mark_validated_complete(store, reviewed)
    prompt = ValidatedReviewInterruptPrompt()

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=ScriptedRegistry({"review-check": [True]}),
        prompt=prompt,
    ).run(lesson_id="reviewed", review_completed=True)

    [record] = store.verification_records((*COURSE_PATH, "reviewed", "do-work"))
    cursor = store.session_cursor(COURSE_PATH)
    assert prompt.presented_checks == ["review-check"]
    assert record.status is VerificationStatus.PASSED
    assert record.attempt_count == 1
    assert record.evidence == "original safe evidence"
    assert (
        store.lesson_completion_source((*COURSE_PATH, "reviewed"))
        is CompletionSource.VALIDATED
    )
    assert cursor is not None
    assert cursor.verification_id == "review-check"
    assert outcome.action is SessionAction.SAVE_AND_EXIT


def test_completion_menu_review_reruns_validated_lesson_checks(
    tmp_path: Path,
) -> None:
    reviewed = Lesson(
        id="reviewed",
        title="Reviewed",
        steps=(
            Step(
                id="review-step",
                title="Review",
                instructions="Review the work.",
                verifications=(verification("review-check"),),
            ),
        ),
    )
    current = Lesson(
        id="current",
        title="Current",
        steps=(
            Step(
                id="current-step",
                title="Current",
                instructions="Complete the current work.",
                verifications=(verification("current-check"),),
            ),
        ),
    )
    course = Course(
        collection_id=COURSE_PATH[0],
        id=COURSE_PATH[1],
        title="Operations",
        lessons=(reviewed, current),
        environment=EnvironmentPolicy(EnvironmentScope.NONE),
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    mark_validated_complete(store, reviewed)
    prompt = ValidatedMenuReviewPrompt()

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=ScriptedRegistry({"current-check": [True], "review-check": [True]}),
        prompt=prompt,
    ).run()

    [reviewed_record] = store.verification_records(
        (*COURSE_PATH, "reviewed", "review-step")
    )
    assert prompt.presented_checks == [
        ("current", "current-check"),
        ("reviewed", "review-check"),
    ]
    assert reviewed_record.attempt_count == 2
    assert reviewed_record.evidence == "original safe evidence"
    assert outcome.lesson_id == "reviewed"


def test_none_scope_save_avoids_provider_and_preserves_existing_environment(
    tmp_path: Path,
) -> None:
    course = course_with_steps(
        Step(
            id="inspect",
            title="Inspect",
            instructions="Inspect the system.",
            verifications=(verification("resume-check"),),
        )
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    retained = store.create_environment(
        EnvironmentRecord(
            id="retained-course-environment",
            collection_id=COURSE_PATH[0],
            course_id=COURSE_PATH[1],
            lesson_id="earlier",
            attempt_id=None,
            profile_name="lab",
            provider_type="fake",
            phase=EnvironmentPhase.RUNNING,
            environment_scope=EnvironmentScope.COURSE,
        )
    )

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=LifecycleService(store, ProviderAccessForbidden(), tmp_path),
        validators=FailingRegistry(),
        prompt=SavingPrompt({}),
        provider=ProviderAccessForbidden(),
    ).run()

    assert outcome.action is SessionAction.SAVE_AND_EXIT
    assert store.get_environment(retained.id) == retained
    assert store.verification_records((*COURSE_PATH, "basics", "inspect")) == []
    assert (
        store.step_statuses((*COURSE_PATH, "basics"))["inspect"]
        is StepStatus.IN_PROGRESS
    )


def test_environment_scope_reports_missing_profile_before_lifecycle_access(
    tmp_path: Path,
) -> None:
    lesson = Lesson(
        id="basics",
        title="Basics",
        steps=(
            Step(
                id="inspect",
                title="Inspect",
                instructions="Inspect the system.",
                verifications=(verification("resume-check"),),
            ),
        ),
    )
    course = Course(
        collection_id=COURSE_PATH[0],
        id=COURSE_PATH[1],
        title="Operations",
        lessons=(lesson,),
        environment=EnvironmentPolicy(EnvironmentScope.COURSE, "demo.vm"),
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    lifecycle = LifecycleAccessForbidden()

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=lifecycle,
        validators=ScriptedRegistry({"resume-check": [True]}),
        prompt=NavigationPrompt({}),
    ).run()

    assert outcome.action is SessionAction.ERROR
    assert outcome.error is not None
    assert "course demo/operations" in outcome.error
    assert "lesson basics" in outcome.error
    assert "provider profile" in outcome.error.lower()
    assert lifecycle.called is False


def test_declined_lesson_replacement_saves_without_starting_or_mutating(
    tmp_path: Path,
) -> None:
    lesson = Lesson(
        id="second",
        title="Second",
        steps=(
            Step(
                id="do-work",
                title="Do work",
                instructions="Complete the work.",
                verifications=(verification("confirm-work"),),
            ),
        ),
    )
    course = Course(
        collection_id=COURSE_PATH[0],
        id=COURSE_PATH[1],
        title="Operations",
        lessons=(lesson,),
        environment=EnvironmentPolicy(EnvironmentScope.LESSON, "demo.vm"),
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    lifecycle = ReplacingLifecycle()

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=lifecycle,
        validators=ScriptedRegistry({"confirm-work": [True]}),
        prompt=CancellingReplacementPrompt({}),
        profile=FakeProfile(),
        provider_type="fake",
    ).run()

    assert lifecycle.calls == [("second", False)]
    assert store.lesson_statuses(*COURSE_PATH) == {}
    assert store.session_cursor(COURSE_PATH) is None
    assert outcome.action is SessionAction.SAVE_AND_EXIT


def test_lesson_completion_review_choice_can_explicitly_review_legacy_lesson(
    tmp_path: Path,
) -> None:
    lessons = tuple(
        Lesson(
            id=lesson_id,
            title=lesson_id.title(),
            steps=(
                Step(
                    id="do-work",
                    title="Do work",
                    instructions="Complete the work.",
                    verifications=(verification("confirm-work"),),
                ),
            ),
        )
        for lesson_id in ("legacy", "current")
    )
    course = Course(
        collection_id=COURSE_PATH[0],
        id=COURSE_PATH[1],
        title="Operations",
        lessons=lessons,
        environment=EnvironmentPolicy(EnvironmentScope.NONE),
    )
    store = StateStore(tmp_path / "state.db")
    store.initialize()
    mark_legacy_complete(store, "legacy")
    prompt = ReviewPrompt(
        {"current": SessionAction.REVIEW, "legacy": SessionAction.EXIT}
    )

    outcome = CourseSession(
        course=course,
        store=store,
        lifecycle=NoEnvironmentLifecycle(),
        validators=ScriptedRegistry({"confirm-work": [True, True]}),
        prompt=prompt,
    ).run()

    assert prompt.presented_lessons == ["current", "legacy"]
    assert prompt.legacy_labels == ["legacy"]
    assert (
        store.lesson_completion_source((*COURSE_PATH, "legacy"))
        is CompletionSource.VALIDATED
    )
    assert outcome.lesson_id == "legacy"
