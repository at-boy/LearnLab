from __future__ import annotations

import sys
import time
from collections.abc import Callable, Mapping
from importlib.resources import files
from pathlib import Path
from types import TracebackType
from typing import Protocol, TextIO

import typer

from learnlab.config import (
    ProxmoxProfile,
    Settings,
    load_requested_profiles,
    load_settings,
    resolve_token_secret,
    state_dir,
)
from learnlab.curriculum import (
    Course,
    CurriculumCatalog,
    CurriculumError,
    EnvironmentPolicy,
    EnvironmentScope,
    Lesson,
    Step,
    Verification,
    VerificationType,
)
from learnlab.errors import ConfigurationError, LearnLabError, redact
from learnlab.lifecycle import (
    PROVISIONING_INTERRUPTED_GUIDANCE,
    EnvironmentResolution,
    LifecycleService,
)
from learnlab.progress import ProgressEvent, ProgressKind, ProgressObserver
from learnlab.providers.base import Provider
from learnlab.providers.proxmox import ProxmoxProvider
from learnlab.providers.registry import build_provider
from learnlab.session import (
    CourseSession,
    SessionAction,
    SessionDependencies,
    SessionOutcome,
    SessionPrompt,
)
from learnlab.ssh import SshExecutor
from learnlab.state import (
    CompletionSource,
    ProgressStatus,
    StateConflictError,
    StateStore,
    resolve_default_state_db,
)
from learnlab.validation import (
    ManualConfirmationValidator,
    ProviderCheckValidator,
    RemoteCommandValidator,
    TextEvidenceValidator,
    ValidatorRegistry,
    VerificationResult,
)

CatalogFactory = Callable[[], CurriculumCatalog]
StateStoreFactory = Callable[[], StateStore]


class ProviderFactory(Protocol):
    def __call__(
        self,
        settings: Settings,
        profile_name: str,
        secret: str | None = None,
    ) -> Provider: ...


class TerminalProgressRenderer(ProgressObserver):
    """Render lifecycle progress safely for terminals and captured logs."""

    _SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(
        self,
        output: TextIO | None = None,
        *,
        is_terminal: bool | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._output = output if output is not None else sys.stdout
        self._is_terminal = (
            self._output.isatty() if is_terminal is None else is_terminal
        )
        self._clock = clock
        self._active_line = False
        self._rendered_width = 0
        self._closed = False

    def __enter__(self) -> TerminalProgressRenderer:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def on_progress(self, event: ProgressEvent) -> None:
        if self._closed:
            return
        attempt = f" (attempt {event.attempt})" if event.attempt is not None else ""
        if self._is_terminal:
            frame_index = int(self._clock() * 10) % len(self._SPINNER_FRAMES)
            frame = self._SPINNER_FRAMES[frame_index]
            rendered = (
                f"{frame} {event.message}{attempt} [{event.elapsed_seconds:.1f}s]"
            )
            padding = " " * max(0, self._rendered_width - len(rendered))
            self._output.write(f"\r{rendered}{padding}")
            self._active_line = True
            self._rendered_width = len(rendered)
        else:
            self._output.write(f"{event.message}{attempt}\n")
        self._output.flush()
        if event.kind is ProgressKind.ENVIRONMENT_READY:
            self._finish_line()

    def close(self) -> None:
        if self._closed:
            return
        self._finish_line()
        self._closed = True

    def _finish_line(self) -> None:
        if self._is_terminal and self._active_line:
            self._output.write("\n")
            self._output.flush()
        self._active_line = False
        self._rendered_width = 0


class TyperSessionPrompt(SessionPrompt):
    """Translate the session prompt protocol into terminal interactions."""

    def __init__(self, course: Course) -> None:
        self._course = course

    def present_lesson(self, course: Course, lesson: Lesson) -> None:
        typer.echo(f"Lesson: {lesson.title}")

    def present_step(
        self, lesson: Lesson, step: Step, position: int, total: int
    ) -> None:
        typer.echo()
        typer.echo(f"Step {position} of {total}: {step.title}")
        typer.echo(step.instructions)

    def begin_verification(
        self,
        lesson: Lesson,
        step: Step,
        verification: Verification,
        position: int,
        total: int,
    ) -> SessionAction:
        typer.echo()
        typer.echo(f"Verification {position} of {total}: {verification.id}")
        response = typer.prompt(
            "Press Enter when ready for LearnLab to check it, "
            "or type q to save and exit",
            default="",
            show_default=False,
        )
        return (
            SessionAction.SAVE_AND_EXIT
            if response.strip().lower() == "q"
            else SessionAction.READY
        )

    def present_result(
        self, verification: Verification, result: VerificationResult
    ) -> None:
        status = "PASS" if result.passed else "FAIL"
        attestation = " (self-attested)" if result.self_attested else ""
        typer.echo(f"{status}{attestation}: {result.summary}")

    def failed_verification(
        self, verification: Verification, result: VerificationResult
    ) -> SessionAction:
        while True:
            response = (
                typer.prompt(
                    "Retry this verification [r], or save and exit [q]",
                    default="r",
                    show_default=False,
                )
                .strip()
                .lower()
            )
            if response in {"r", "retry"}:
                return SessionAction.RETRY
            if response in {"q", "quit", "save", "exit"}:
                return SessionAction.SAVE_AND_EXIT
            typer.echo("Choose r to retry or q to save and exit")

    def lesson_completed(
        self, course: Course, lesson: Lesson, next_lesson: Lesson | None
    ) -> SessionAction:
        typer.echo()
        typer.echo(f"Lesson complete: {lesson.title}")
        if next_lesson is not None:
            typer.echo(f"Next lesson: {next_lesson.title}")
            choices = "Continue [c], review a lesson [r], or save and exit [q]"
        else:
            typer.echo("Course complete.")
            choices = "Review a lesson [r], or save and exit [q]"
        while True:
            response = (
                typer.prompt(
                    choices,
                    default="q",
                    show_default=False,
                )
                .strip()
                .lower()
            )
            if next_lesson is not None and response in {"c", "continue"}:
                return SessionAction.CONTINUE
            if response in {"r", "review"}:
                return SessionAction.REVIEW
            if response in {"q", "quit", "save", "exit"}:
                return SessionAction.SAVE_AND_EXIT
            typer.echo("Choose one of the listed actions")

    def choose_review_lesson(self, course: Course) -> str | None:
        typer.echo("Lessons available for review:")
        for position, lesson in enumerate(course.lessons, start=1):
            typer.echo(f"{position}. {lesson.title}")
        while True:
            response = (
                typer.prompt(
                    "Select a lesson number, or q to save and exit",
                    default="q",
                    show_default=False,
                )
                .strip()
                .lower()
            )
            if response in {"q", "quit", "save", "exit"}:
                return None
            if response.isdigit() and 1 <= int(response) <= len(course.lessons):
                return course.lessons[int(response) - 1].id
            typer.echo(f"Choose a lesson number from 1 to {len(course.lessons)}")

    def confirm_environment_change(
        self, resolution: EnvironmentResolution, lesson: Lesson
    ) -> bool:
        environment = resolution.environment
        if environment is None:
            typer.echo("No recorded environment target is available.")
            return False
        owner_id = environment.lesson_owner_id or environment.lesson_id
        existing_lesson = next(
            (
                candidate
                for candidate in self._course.lessons
                if candidate.id == owner_id
            ),
            None,
        )
        typer.echo("Existing environment to replace:")
        typer.echo(f"  Profile: {environment.profile_name}")
        vm_label = (
            str(environment.vmid) if environment.vmid is not None else "unallocated"
        )
        typer.echo(f"  VM {vm_label}")
        typer.echo(f"  Expected name: {environment.expected_vm_name or 'unknown'}")
        typer.echo(
            "  Current lesson: "
            f"{existing_lesson.title if existing_lesson is not None else owner_id}"
        )
        typer.echo(f"  Requested lesson: {lesson.title}")
        action = "Recreate" if resolution.recreation_required else "Replace"
        return typer.confirm(f"{action} this environment?", default=False)

    def legacy_completion(self, lesson: Lesson) -> None:
        typer.echo(f"{lesson.title}: completed before step verification tracking")

    def ask_text(self, prompt: str) -> str:
        return str(typer.prompt(prompt))

    def confirm(self, prompt: str) -> bool:
        return typer.confirm(prompt, default=False)


class LifecycleFactory(Protocol):
    def __call__(
        self,
        store: StateStore,
        provider: Provider | Mapping[str, Provider | Exception],
        state_root: Path,
        *,
        secrets: set[str] | None = None,
        progress: ProgressObserver = ...,
    ) -> LifecycleService: ...


app = typer.Typer()
provider_app = typer.Typer()
progress_app = typer.Typer()
app.add_typer(provider_app, name="provider")
app.add_typer(progress_app, name="progress")


def _build_provider(
    settings: Settings,
    profile_name: str,
    secret: str | None = None,
) -> Provider:
    if secret is None:
        return build_provider(settings, profile_name)
    return ProxmoxProvider(settings.provider(profile_name), secret)


def _default_validator_registry() -> ValidatorRegistry:
    registry = ValidatorRegistry()
    registry.register(VerificationType.REMOTE_COMMAND, RemoteCommandValidator())
    registry.register(VerificationType.TEXT_EVIDENCE, TextEvidenceValidator())
    registry.register(
        VerificationType.MANUAL_CONFIRMATION, ManualConfirmationValidator()
    )
    registry.register(VerificationType.PROVIDER_CHECK, ProviderCheckValidator())
    return registry


provider_factory: ProviderFactory = _build_provider
state_root: Callable[[], Path] = state_dir
lifecycle_factory: LifecycleFactory = LifecycleService
progress_renderer_factory: Callable[[], TerminalProgressRenderer] = (
    TerminalProgressRenderer
)
validator_registry_factory: Callable[[], ValidatorRegistry] = (
    _default_validator_registry
)

_PROVIDER_TYPES_BY_CAPABILITY = {"proxmox.vm": "proxmox"}


class _LazySessionDependencyResolver:
    """Resolve provider configuration only when a provider lesson is entered."""

    def __init__(
        self,
        *,
        store: StateStore,
        root: Path,
        progress: ProgressObserver,
        secrets: set[str],
        provider_profile: str | None,
    ) -> None:
        self._store = store
        self._root = root
        self._progress = progress
        self._secrets = secrets
        self._provider_profile = provider_profile
        self._cache: dict[EnvironmentPolicy, SessionDependencies] = {}
        self._provider_dependencies: SessionDependencies | None = None

    def resolve(self, policy: EnvironmentPolicy) -> SessionDependencies:
        try:
            return self._cache[policy]
        except KeyError:
            pass
        if policy.scope is EnvironmentScope.NONE:
            dependencies = SessionDependencies(
                lifecycle=lifecycle_factory(
                    self._store,
                    {},
                    self._root,
                    secrets=self._secrets,
                    progress=self._progress,
                )
            )
            self._cache[policy] = dependencies
            return dependencies

        capability = policy.provider_capability
        provider_type = (
            _PROVIDER_TYPES_BY_CAPABILITY.get(capability)
            if capability is not None
            else None
        )
        if provider_type is None:
            raise ConfigurationError(
                f"Unsupported provider capability: {capability or 'missing'}"
            )

        if self._provider_dependencies is None:
            settings = load_settings()
            profile_name = self._provider_profile or settings.default_provider
            profile = settings.provider(profile_name)
            _render_tls_warning(profile)
            secret = resolve_token_secret(profile)
            self._secrets.add(secret)
            provider = provider_factory(settings, profile_name, secret)
            self._provider_dependencies = SessionDependencies(
                lifecycle=lifecycle_factory(
                    self._store,
                    provider,
                    self._root,
                    secrets=self._secrets,
                    progress=self._progress,
                ),
                profile=profile,
                provider_type=provider_type,
                provider=provider,
                ssh_executor=SshExecutor(self._root, secrets=self._secrets),
            )
        dependencies = self._provider_dependencies
        self._cache[policy] = dependencies
        return dependencies


def _default_catalog() -> CurriculumCatalog:
    return CurriculumCatalog(files("learnlab").joinpath("collections"))


def _default_state_store() -> StateStore:
    return StateStore(resolve_default_state_db(state_root()))


catalog_factory: CatalogFactory = _default_catalog
state_store_factory: StateStoreFactory = _default_state_store


@provider_app.command("test")
def provider_test(profile_name: str) -> None:
    """Check the configured provider profile without changing infrastructure."""
    try:
        settings = load_settings()
        profile = settings.provider(profile_name)
        typer.echo(f"Provider profile: {profile_name}")
        _render_tls_warning(profile)
        provider = provider_factory(settings, profile_name)
        health = provider.health_check()
    except LearnLabError as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(
            code=2 if isinstance(error, ConfigurationError) else 3
        ) from None

    for check in health.checks:
        status = "PASS" if check.ok else "FAIL"
        typer.echo(f"{status} {check.name}: {check.detail}")
    for warning in health.warnings:
        typer.echo(f"WARNING: {warning}")
    if health.provider_error:
        raise typer.Exit(code=3)
    if any(check.required and not check.ok for check in health.checks):
        raise typer.Exit(code=1)


@app.command("start")
def start_course(
    course_path: str,
    provider_profile: str | None = typer.Option(None, "--provider"),
) -> None:
    """Start or resume an interactive course session."""
    _run_course_session(course_path, provider_profile, require_existing=False)


@app.command("resume")
def resume_course(
    course_path: str,
    provider_profile: str | None = typer.Option(None, "--provider"),
) -> None:
    """Resume a course that already has local progress or environment state."""
    _run_course_session(course_path, provider_profile, require_existing=True)


def _run_course_session(
    course_path: str,
    provider_profile: str | None,
    *,
    require_existing: bool,
) -> None:
    """Construct terminal adapters and delegate course behavior to CourseSession."""
    secrets: set[str] = set()
    try:
        course = catalog_factory().load_course(course_path)
        store = state_store_factory()
        store.initialize()
        if require_existing and not _course_has_state(store, course):
            raise ConfigurationError(
                f"No saved state for {course_path}; use learnlab start {course_path}"
            )

        statuses = store.lesson_statuses(course.collection_id, course.id)
        default_index = _default_lesson_index(course, statuses)
        _render_lessons(course, statuses, default_index)
        lesson = _prompt_for_lesson(course, default_index)
        policy = course.effective_environment(lesson)
        typer.echo(f"Selected lesson: {lesson.title}")
        _render_environment_policy(policy.scope, policy.provider_capability)

        root = state_root()
        renderer = progress_renderer_factory()
        dependency_resolver = _LazySessionDependencyResolver(
            store=store,
            root=root,
            progress=renderer,
            secrets=secrets,
            provider_profile=provider_profile,
        )
        session = CourseSession(
            course=course,
            store=store,
            lifecycle=None,
            validators=validator_registry_factory(),
            prompt=TyperSessionPrompt(course),
            secrets=secrets,
            dependency_resolver=dependency_resolver,
        )
        with renderer:
            outcome = session.run(
                lesson_id=lesson.id,
                review_completed=(statuses.get(lesson.id) is ProgressStatus.COMPLETED),
            )
    except LearnLabError as error:
        _exit_with_error(error, secrets)

    _render_session_outcome(course_path, outcome, secrets)


@app.command("destroy")
def destroy_all(
    yes: bool = typer.Option(False, "--yes"),
    preserve_progress: bool = typer.Option(False, "--preserve-progress"),
    erase_progress: bool = typer.Option(False, "--erase-progress"),
) -> None:
    """Destroy every recorded environment for the current user."""
    if preserve_progress and erase_progress:
        typer.echo(
            "Error: choose exactly one of --preserve-progress or --erase-progress"
        )
        raise typer.Exit(code=2)
    if not yes and preserve_progress:
        typer.echo("Error: --preserve-progress requires --yes")
        raise typer.Exit(code=2)
    if not yes and erase_progress:
        typer.echo("Error: --erase-progress requires --yes")
        raise typer.Exit(code=2)
    if yes and not (preserve_progress or erase_progress):
        typer.echo("Error: --yes requires --preserve-progress or --erase-progress")
        raise typer.Exit(code=2)

    try:
        store = state_store_factory()
    except LearnLabError as error:
        _exit_with_error(error)
    state_exists = store.db_path.exists()
    if state_exists:
        store.initialize()
    targets = tuple(store.list_environments()) if state_exists else ()
    profile_names = tuple(dict.fromkeys(target.profile_name for target in targets))
    loaded_profiles = load_requested_profiles(profile_names) if targets else None
    typer.echo("Destroy targets:")
    if not targets:
        typer.echo("  No recorded environments")
    for target in targets:
        vm_label = str(target.vmid) if target.vmid is not None else "unallocated"
        node_label = target.node or "unknown"
        typer.echo(
            f"  Profile: {target.profile_name} | VM {vm_label} | "
            f"Node: {node_label} | "
            f"Course: {target.collection_id}/{target.course_id} | "
            f"Phase: {target.phase.value}"
        )
        typer.echo(f"    Endpoint: {target.provider_endpoint or 'unknown'}")
        typer.echo(f"    Fingerprint: {target.provider_fingerprint or 'unknown'}")
        typer.echo(f"    Expected VM name: {target.expected_vm_name or 'unknown'}")
        if (
            loaded_profiles is not None
            and target.profile_name not in loaded_profiles.errors
        ):
            configured = loaded_profiles.settings.provider(target.profile_name)
            typer.echo(f"    Configured endpoint: {configured.api_url}")
            typer.echo(f"    Configured fingerprint: {configured.fingerprint}")
            _render_tls_warning(configured, prefix="    ")

    if not yes and not typer.confirm("Destroy all listed environments?"):
        typer.echo("Cancelled.")
        return

    if preserve_progress:
        preserve_completed = True
    elif erase_progress:
        preserve_completed = False
    else:
        preserve_completed = typer.confirm("Preserve completed lessons?", default=True)

    if not state_exists:
        typer.echo("Destroyed environments: 0")
        return

    secrets: set[str] = set()
    providers: dict[str, Provider | Exception] = {}
    if targets and loaded_profiles is not None:
        providers.update(loaded_profiles.errors)
        for profile_name in profile_names:
            if profile_name in loaded_profiles.errors:
                continue
            try:
                profile = loaded_profiles.settings.provider(profile_name)
                secret = resolve_token_secret(profile)
                secrets.add(secret)
                providers[profile_name] = provider_factory(
                    loaded_profiles.settings, profile_name
                )
            except LearnLabError as error:
                providers[profile_name] = error

    try:
        lifecycle = lifecycle_factory(
            store,
            providers,
            state_root(),
            secrets=secrets,
        )
        summary = lifecycle.destroy_all(preserve_completed, targets)
    except LearnLabError as error:
        _exit_with_error(error, secrets)

    if summary.failed:
        retained_by_id = {
            environment.id: environment for environment in store.list_environments()
        }
        for environment_id in summary.failed:
            typer.echo(f"Retained environment: {environment_id}")
            if retained := retained_by_id.get(environment_id):
                vm_label = (
                    str(retained.vmid) if retained.vmid is not None else "unallocated"
                )
                typer.echo(
                    f"  Profile: {retained.profile_name} | VM {vm_label} | "
                    f"Node: {retained.node or 'unknown'} | "
                    f"Course: {retained.collection_id}/{retained.course_id} | "
                    f"Phase: {retained.phase.value}"
                )
                if retained.error_summary:
                    typer.echo(f"  Error: {redact(retained.error_summary, secrets)}")
        raise typer.Exit(code=3)

    typer.echo(f"Destroyed environments: {len(summary.destroyed)}")


@app.command("reset")
def reset_scope(
    scope: str,
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    """Reset progress and attempt history for one collection or course."""
    try:
        collection_id, course_id = _split_reset_scope(scope)
        store = state_store_factory()
        store.initialize()
        affected_courses, affected_lessons = _reset_scope_counts(
            store, collection_id, course_id
        )
        typer.echo(f"Scope: {scope}")
        typer.echo(f"Affected courses: {affected_courses}")
        typer.echo(f"Affected lessons: {affected_lessons}")

        matching_environments = [
            environment
            for environment in store.list_environments()
            if environment.collection_id == collection_id
            and (course_id is None or environment.course_id == course_id)
        ]
        if matching_environments:
            raise StateConflictError(
                "Run learnlab destroy for matching environments before "
                "resetting progress"
            )

        if not yes and not typer.confirm("Continue?"):
            typer.echo("Cancelled.")
            return

        store.reset_scope(collection_id, course_id)
    except LearnLabError as error:
        _exit_with_error(error)

    typer.echo(f"Reset: {scope}")


@progress_app.command("complete")
def progress_complete(
    lesson_path: str,
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    """Administratively override one known curriculum lesson as completed."""
    try:
        collection_id, course_id, lesson_id = _split_lesson_path(lesson_path)
        course = catalog_factory().load_course(f"{collection_id}/{course_id}")
        if lesson_id not in {lesson.id for lesson in course.lessons}:
            raise CurriculumError(f"Unknown lesson: {lesson_id}")
        store = state_store_factory()
        store.initialize()
        typer.echo(
            "This is an administrative override, not verified learning progress."
        )
        typer.echo("Normal learners should complete lessons through start or resume.")
        if not yes and not typer.confirm(f"Mark {lesson_path} as completed?"):
            typer.echo("Cancelled.")
            return
        store.complete_lesson(
            collection_id,
            course_id,
            lesson_id,
            source=CompletionSource.MANUAL_OVERRIDE,
        )
    except LearnLabError as error:
        _exit_with_error(error)

    typer.echo(f"Completed: {lesson_path}")


def _course_has_state(store: StateStore, course: Course) -> bool:
    course_path = (course.collection_id, course.id)
    return bool(
        store.lesson_statuses(*course_path)
        or store.session_cursor(course_path) is not None
        or store.active_environment(*course_path) is not None
    )


def _render_environment_policy(
    scope: EnvironmentScope, provider_capability: str | None
) -> None:
    capability = f" ({provider_capability})" if provider_capability is not None else ""
    typer.echo(f"Environment policy: {scope.value}{capability}")


def _render_session_outcome(
    course_path: str,
    outcome: SessionOutcome,
    secrets: set[str],
) -> None:
    if outcome.action is SessionAction.PROVISIONING_INTERRUPTED:
        message = redact(
            outcome.error or PROVISIONING_INTERRUPTED_GUIDANCE,
            secrets,
        )
        typer.echo(message)
        raise typer.Exit(code=130)
    if outcome.action is SessionAction.ERROR:
        message = redact(outcome.error or "session operation failed", secrets)
        typer.echo(f"Error: {message}")
        raise typer.Exit(code=3)
    if outcome.action is SessionAction.SAVE_AND_EXIT:
        typer.echo(f"Progress saved. Resume with: learnlab resume {course_path}")


def _default_lesson_index(course: Course, statuses: dict[str, ProgressStatus]) -> int:
    for index, lesson in enumerate(course.lessons):
        if statuses.get(lesson.id) is not ProgressStatus.COMPLETED:
            return index
    return 0


def _render_lessons(
    course: Course,
    statuses: dict[str, ProgressStatus],
    default_index: int,
) -> None:
    typer.echo(f"Course: {course.title}")
    for index, lesson in enumerate(course.lessons):
        status = statuses.get(lesson.id)
        label = ""
        if status is ProgressStatus.COMPLETED:
            label = " [completed]"
        elif status is ProgressStatus.IN_PROGRESS:
            label = " [in progress]"
        elif index == default_index:
            label = " [first incomplete]"
        typer.echo(f"{index + 1}. {lesson.title}{label}")


def _prompt_for_lesson(course: Course, default_index: int) -> Lesson:
    while True:
        selection = int(
            typer.prompt(
                "Select lesson",
                default=default_index + 1,
                type=int,
            )
        )
        if 1 <= selection <= len(course.lessons):
            return course.lessons[selection - 1]
        typer.echo(f"Choose a lesson number from 1 to {len(course.lessons)}")


def _split_lesson_path(lesson_path: str) -> tuple[str, str, str]:
    pieces = lesson_path.split("/")
    if len(pieces) != 3 or not all(pieces):
        raise CurriculumError("Lesson path must use collection/course/lesson")
    return pieces[0], pieces[1], pieces[2]


def _split_reset_scope(scope: str) -> tuple[str, str | None]:
    pieces = scope.split("/")
    if len(pieces) not in {1, 2} or not all(pieces):
        raise CurriculumError("Reset scope must use collection or collection/course")
    return pieces[0], pieces[1] if len(pieces) == 2 else None


def _reset_scope_counts(
    store: StateStore, collection_id: str, course_id: str | None
) -> tuple[int, int]:
    attempts = [
        attempt
        for attempt in store.list_attempts()
        if attempt.collection_id == collection_id
        and (course_id is None or attempt.course_id == course_id)
    ]
    environments = [
        environment
        for environment in store.list_environments()
        if environment.collection_id == collection_id
        and (course_id is None or environment.course_id == course_id)
    ]
    progress = [
        row
        for row in store.list_progress()
        if row[0] == collection_id and (course_id is None or row[1] == course_id)
    ]
    course_ids = {attempt.course_id for attempt in attempts}
    course_ids.update(environment.course_id for environment in environments)
    course_ids.update(row[1] for row in progress)
    if course_id is not None and store.lesson_statuses(collection_id, course_id):
        course_ids.add(course_id)

    lessons = {(attempt.course_id, attempt.lesson_id) for attempt in attempts}
    lessons.update(
        (environment.course_id, environment.lesson_id) for environment in environments
    )
    lessons.update((row[1], row[2]) for row in progress)
    for retained_course_id in course_ids:
        lessons.update(
            (retained_course_id, lesson_id)
            for lesson_id in store.lesson_statuses(collection_id, retained_course_id)
        )
    return len(course_ids), len(lessons)


def _render_tls_warning(profile: ProxmoxProfile, *, prefix: str = "") -> None:
    if not profile.tls_verify:
        typer.echo(f"{prefix}WARNING: TLS certificate verification is disabled")


def _exit_with_error(error: LearnLabError, secrets: set[str] | None = None) -> None:
    message = redact(str(error), secrets or set())
    typer.echo(f"Error: {message}")
    input_error = isinstance(error, (ConfigurationError, CurriculumError))
    raise typer.Exit(code=2 if input_error else 3) from None
