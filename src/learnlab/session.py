"""Provider-neutral orchestration for resumable interactive course sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from learnlab.curriculum import Course, EnvironmentScope, Lesson, Step, Verification
from learnlab.errors import redact
from learnlab.lifecycle import (
    EnvironmentResolution,
    LifecycleService,
    StartProfile,
    StartRequest,
)
from learnlab.providers.base import Provider
from learnlab.ssh import SshExecutor
from learnlab.state import (
    CompletionSource,
    StateStore,
    StepStatus,
    VerificationStatus,
)
from learnlab.validation import (
    ValidationContext,
    ValidationPrompt,
    ValidatorRegistry,
    VerificationResult,
)


class SessionAction(StrEnum):
    """Choices accepted and terminal actions returned by a course session."""

    READY = "ready"
    RETRY = "retry"
    SAVE_AND_EXIT = "save-and-exit"
    CONTINUE = "continue"
    REVIEW = "review"
    EXIT = "exit"
    ERROR = "error"


@dataclass(frozen=True)
class SessionOutcome:
    """Safe result of running an interactive session until its next boundary."""

    action: SessionAction
    lesson_id: str | None
    lesson_completed: bool = False
    course_completed: bool = False
    error: str | None = None


class SessionPrompt(ValidationPrompt, Protocol):
    """UI-neutral prompts and presentation events needed by the state machine."""

    def present_lesson(self, course: Course, lesson: Lesson) -> None: ...

    def present_step(
        self, lesson: Lesson, step: Step, position: int, total: int
    ) -> None: ...

    def begin_verification(
        self,
        lesson: Lesson,
        step: Step,
        verification: Verification,
        position: int,
        total: int,
    ) -> SessionAction: ...

    def present_result(
        self, verification: Verification, result: VerificationResult
    ) -> None: ...

    def failed_verification(
        self, verification: Verification, result: VerificationResult
    ) -> SessionAction: ...

    def lesson_completed(
        self, course: Course, lesson: Lesson, next_lesson: Lesson | None
    ) -> SessionAction: ...

    def choose_review_lesson(self, course: Course) -> str | None: ...

    def confirm_environment_change(
        self, resolution: EnvironmentResolution, lesson: Lesson
    ) -> bool: ...

    def legacy_completion(self, lesson: Lesson) -> None: ...


class CourseSession:
    """Run ordered lesson verifications against durable state."""

    def __init__(
        self,
        *,
        course: Course,
        store: StateStore,
        lifecycle: LifecycleService,
        validators: ValidatorRegistry,
        prompt: SessionPrompt,
        profile: StartProfile | None = None,
        provider_type: str | None = None,
        provider: Provider | None = None,
        ssh_executor: SshExecutor | None = None,
        secrets: set[str] | None = None,
    ) -> None:
        self._course = course
        self._store = store
        self._lifecycle = lifecycle
        self._validators = validators
        self._prompt = prompt
        self._profile = profile
        self._provider_type = provider_type
        self._provider = provider
        self._ssh_executor = ssh_executor
        self._secrets = secrets or set()
        self._current_lesson_id: str | None = None
        self._current_step_id: str | None = None
        self._current_verification_id: str | None = None

    def run(
        self,
        *,
        lesson_id: str | None = None,
        review_completed: bool = False,
    ) -> SessionOutcome:
        """Start or resume at the first incomplete stable curriculum ID."""
        try:
            return self._run_session(lesson_id, review_completed)
        except KeyboardInterrupt:
            return SessionOutcome(
                SessionAction.SAVE_AND_EXIT,
                self._current_lesson_id,
            )
        except Exception as error:
            return SessionOutcome(
                SessionAction.ERROR,
                self._current_lesson_id,
                error=self._contextual_error(error),
            )

    def _run_session(
        self, lesson_id: str | None, review_completed: bool
    ) -> SessionOutcome:
        lesson = (
            self._lesson_by_id(lesson_id)
            if lesson_id is not None
            else self._first_incomplete_lesson()
        )
        if lesson is None:
            return SessionOutcome(
                SessionAction.EXIT,
                None,
                course_completed=True,
            )

        if self._is_completed(lesson):
            if self._is_legacy_completed(lesson):
                self._prompt.legacy_completion(lesson)
            if not review_completed:
                lesson = self._first_incomplete_lesson()
                if lesson is None:
                    return SessionOutcome(
                        SessionAction.EXIT,
                        lesson_id,
                        course_completed=True,
                    )

        reviewing = review_completed and self._is_completed(lesson)
        while True:
            self._current_lesson_id = lesson.id
            outcome = self._run_lesson(lesson, reviewing=reviewing)
            if outcome.action is SessionAction.REVIEW:
                selected_id = self._prompt.choose_review_lesson(self._course)
                if selected_id is None:
                    return SessionOutcome(
                        SessionAction.SAVE_AND_EXIT,
                        lesson.id,
                        lesson_completed=True,
                        course_completed=outcome.course_completed,
                    )
                lesson = self._lesson_by_id(selected_id)
                if self._is_legacy_completed(lesson):
                    self._prompt.legacy_completion(lesson)
                reviewing = self._is_completed(lesson)
                continue
            if outcome.action is not SessionAction.CONTINUE:
                return outcome
            lesson = self._first_incomplete_lesson()
            if lesson is None:
                return SessionOutcome(
                    SessionAction.EXIT,
                    outcome.lesson_id,
                    lesson_completed=True,
                    course_completed=True,
                )
            reviewing = False

    def _run_lesson(self, lesson: Lesson, *, reviewing: bool = False) -> SessionOutcome:
        self._current_step_id = None
        self._current_verification_id = None
        policy = self._course.effective_environment(lesson)
        request = StartRequest(
            course=self._course,
            lesson=lesson,
            profile=self._profile_for_policy(policy.scope),
            provider_type=self._provider_type_for_policy(policy.scope),
        )
        resolution = self._lifecycle.ensure_environment(request, policy)
        if resolution.replacement_required or resolution.recreation_required:
            if not self._prompt.confirm_environment_change(resolution, lesson):
                return SessionOutcome(
                    SessionAction.SAVE_AND_EXIT,
                    lesson.id,
                )
            resolution = self._lifecycle.ensure_environment(
                request,
                policy,
                replace_confirmed=True,
            )
        if not self._is_completed(lesson):
            self._store.start_lesson(
                self._course.collection_id, self._course.id, lesson.id
            )
        self._prompt.present_lesson(self._course, lesson)

        lesson_path = (self._course.collection_id, self._course.id, lesson.id)
        for step_position, step in enumerate(lesson.steps, start=1):
            self._current_step_id = step.id
            statuses = self._store.step_statuses(lesson_path)
            if statuses.get(step.id) is StepStatus.COMPLETED and not reviewing:
                continue
            step_path = (*lesson_path, step.id)
            self._store.start_step(step_path)
            self._prompt.present_step(lesson, step, step_position, len(lesson.steps))

            records = self._store.verification_records(step_path)
            passed_ids = (
                set()
                if reviewing
                else {
                    record.verification_id
                    for record in records
                    if record.status is VerificationStatus.PASSED
                }
            )
            for verification_position, verification in enumerate(
                step.verifications, start=1
            ):
                if verification.id in passed_ids:
                    continue
                self._current_verification_id = verification.id
                self._store.set_session_cursor(
                    (self._course.collection_id, self._course.id),
                    lesson.id,
                    step.id,
                    verification.id,
                )
                action = self._prompt.begin_verification(
                    lesson,
                    step,
                    verification,
                    verification_position,
                    len(step.verifications),
                )
                if action is SessionAction.SAVE_AND_EXIT:
                    return SessionOutcome(action, lesson.id)
                while True:
                    result = self._safe_result(
                        self._validators.validate(
                            self._validation_context(resolution), verification
                        )
                    )
                    self._store.record_verification_result(
                        step_path,
                        verification.id,
                        passed=result.passed,
                        evidence=result.evidence,
                        validator_type=result.validator_type,
                        self_attested=result.self_attested,
                    )
                    self._store.set_session_cursor(
                        (self._course.collection_id, self._course.id),
                        lesson.id,
                        step.id,
                        verification.id,
                    )
                    self._prompt.present_result(verification, result)
                    if result.passed:
                        break
                    failure_action = self._prompt.failed_verification(
                        verification, result
                    )
                    if failure_action is SessionAction.RETRY:
                        continue
                    return SessionOutcome(SessionAction.SAVE_AND_EXIT, lesson.id)

            self._store.complete_step(
                step_path, tuple(item.id for item in step.verifications)
            )

        self._store.complete_lesson_validated(
            lesson_path, tuple(step.id for step in lesson.steps)
        )
        self._store.set_session_cursor(
            (self._course.collection_id, self._course.id), lesson.id
        )
        next_lesson = self._first_incomplete_lesson()
        action = self._prompt.lesson_completed(self._course, lesson, next_lesson)
        return SessionOutcome(
            action,
            lesson.id,
            lesson_completed=True,
            course_completed=next_lesson is None,
        )

    def _safe_result(self, result: VerificationResult) -> VerificationResult:
        """Return a bounded immutable copy safe for storage and presentation."""
        evidence = (
            redact(result.evidence, self._secrets)
            if result.evidence is not None
            else None
        )
        return VerificationResult(
            passed=result.passed,
            summary=redact(result.summary, self._secrets),
            validator_type=result.validator_type,
            self_attested=result.self_attested,
            evidence=evidence,
            completed_at=datetime.now(UTC).isoformat(),
        )

    def _contextual_error(self, error: Exception) -> str:
        context = [f"course {self._course.collection_id}/{self._course.id}"]
        if self._current_lesson_id is not None:
            context.append(f"lesson {self._current_lesson_id}")
        if self._current_step_id is not None:
            context.append(f"step {self._current_step_id}")
        if self._current_verification_id is not None:
            context.append(f"check {self._current_verification_id}")
        summary = redact(str(error), self._secrets) or "session operation failed"
        return f"{'; '.join(context)}: {summary}"[:500]

    def _first_incomplete_lesson(self) -> Lesson | None:
        completed_ids = self._store.completed_lessons(
            self._course.collection_id, self._course.id
        )
        return next(
            (
                lesson
                for lesson in self._course.lessons
                if lesson.id not in completed_ids
            ),
            None,
        )

    def _lesson_by_id(self, lesson_id: str) -> Lesson:
        for lesson in self._course.lessons:
            if lesson.id == lesson_id:
                return lesson
        raise ValueError(f"Course has no lesson with ID {lesson_id}")

    def _is_completed(self, lesson: Lesson) -> bool:
        return lesson.id in self._store.completed_lessons(
            self._course.collection_id, self._course.id
        )

    def _is_legacy_completed(self, lesson: Lesson) -> bool:
        return (
            self._store.lesson_completion_source(
                (self._course.collection_id, self._course.id, lesson.id)
            )
            is CompletionSource.LEGACY
        )

    def _profile_for_policy(self, scope: EnvironmentScope) -> StartProfile:
        if self._profile is not None:
            return self._profile
        if scope is EnvironmentScope.NONE:
            return _NoEnvironmentProfile()
        raise ValueError("A provider profile is required for this lesson")

    def _provider_type_for_policy(self, scope: EnvironmentScope) -> str:
        if self._provider_type is not None:
            return self._provider_type
        if scope is EnvironmentScope.NONE:
            return "none"
        raise ValueError("A provider type is required for this lesson")

    def _validation_context(
        self, resolution: EnvironmentResolution
    ) -> ValidationContext:
        return ValidationContext(
            state_store=self._store,
            profile=self._profile,
            environment=resolution.environment,
            ssh_executor=self._ssh_executor,
            provider=self._provider,
            prompt=self._prompt,
        )


@dataclass(frozen=True)
class _NoEnvironmentProfile:
    name: str = "none"
    node: str = ""
    ssh_user: str = ""
    ssh_identity_file: Path = Path()
