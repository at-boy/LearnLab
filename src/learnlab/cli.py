from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

import typer

from learnlab.config import (
    Settings,
    load_requested_profiles,
    load_settings,
    resolve_token_secret,
    state_dir,
)
from learnlab.curriculum import Course, CurriculumCatalog, CurriculumError, Lesson
from learnlab.errors import ConfigurationError, LearnLabError, redact
from learnlab.lifecycle import LifecycleService, StartRequest
from learnlab.providers.base import Provider
from learnlab.providers.registry import build_provider
from learnlab.state import ProgressStatus, StateConflictError, StateStore

ProviderFactory = Callable[[Settings, str], Provider]
CatalogFactory = Callable[[], CurriculumCatalog]
StateStoreFactory = Callable[[], StateStore]


class LifecycleFactory(Protocol):
    def __call__(
        self,
        store: StateStore,
        provider: Provider | Mapping[str, Provider | Exception],
        state_root: Path,
        *,
        secrets: set[str] | None = None,
    ) -> LifecycleService: ...


app = typer.Typer()
provider_app = typer.Typer()
progress_app = typer.Typer()
app.add_typer(provider_app, name="provider")
app.add_typer(progress_app, name="progress")
provider_factory: ProviderFactory = build_provider
state_root: Callable[[], Path] = state_dir
lifecycle_factory: LifecycleFactory = LifecycleService


def _default_catalog() -> CurriculumCatalog:
    return CurriculumCatalog(Path(__file__).resolve().parents[2] / "collections")


def _default_state_store() -> StateStore:
    return StateStore(state_root() / "state.db")


catalog_factory: CatalogFactory = _default_catalog
state_store_factory: StateStoreFactory = _default_state_store


@provider_app.command("test")
def provider_test(profile_name: str) -> None:
    """Check the configured provider profile without changing infrastructure."""
    try:
        settings = load_settings()
        profile = settings.provider(profile_name)
        typer.echo(f"Provider profile: {profile_name}")
        if not profile.tls_verify:
            typer.echo("WARNING: TLS certificate verification is disabled")
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
    """Start a selected lesson from an ordered course."""
    secrets: set[str] = set()
    try:
        course = catalog_factory().load_course(course_path)
        store = state_store_factory()
        store.initialize()
        if store.active_environment(course.collection_id, course.id) is not None:
            raise StateConflictError(
                "Course already has an environment; run learnlab destroy first"
            )

        statuses = store.lesson_statuses(course.collection_id, course.id)
        default_index = _default_lesson_index(course, statuses)
        _render_lessons(course, statuses, default_index)
        lesson = _prompt_for_lesson(course, default_index)

        settings = load_settings()
        profile_name = provider_profile or settings.default_provider
        profile = settings.provider(profile_name)
        secret = resolve_token_secret(profile)
        secrets.add(secret)
        provider = provider_factory(settings, profile_name)
        lifecycle = lifecycle_factory(
            store,
            provider,
            state_root(),
            secrets=secrets,
        )
        started = lifecycle.start(
            StartRequest(
                course=course,
                lesson=lesson,
                profile=profile,
                provider_type="proxmox",
            )
        )
        store.start_lesson(course.collection_id, course.id, lesson.id)
    except LearnLabError as error:
        _exit_with_error(error, secrets)

    typer.echo(f"SSH: {started.ssh_command}")
    typer.echo(f"Lesson: {lesson.title}")
    for number, step in enumerate(lesson.steps, start=1):
        typer.echo(f"{number}. {step.title}")
        typer.echo(step.content)


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

    store = state_store_factory()
    state_exists = store.db_path.exists()
    targets = tuple(store.list_environments()) if state_exists else ()
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
    if targets:
        profile_names = tuple(dict.fromkeys(target.profile_name for target in targets))
        loaded_profiles = load_requested_profiles(profile_names)
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
def progress_complete(lesson_path: str) -> None:
    """Explicitly mark one known curriculum lesson completed."""
    try:
        collection_id, course_id, lesson_id = _split_lesson_path(lesson_path)
        course = catalog_factory().load_course(f"{collection_id}/{course_id}")
        if lesson_id not in {lesson.id for lesson in course.lessons}:
            raise CurriculumError(f"Unknown lesson: {lesson_id}")
        store = state_store_factory()
        store.initialize()
        store.complete_lesson(collection_id, course_id, lesson_id)
    except LearnLabError as error:
        _exit_with_error(error)

    typer.echo(f"Completed: {lesson_path}")


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
    course_ids = {attempt.course_id for attempt in attempts}
    course_ids.update(environment.course_id for environment in environments)
    if course_id is not None and store.lesson_statuses(collection_id, course_id):
        course_ids.add(course_id)

    lessons = {(attempt.course_id, attempt.lesson_id) for attempt in attempts}
    lessons.update(
        (environment.course_id, environment.lesson_id) for environment in environments
    )
    for retained_course_id in course_ids:
        lessons.update(
            (retained_course_id, lesson_id)
            for lesson_id in store.lesson_statuses(collection_id, retained_course_id)
        )
    return len(course_ids), len(lessons)


def _exit_with_error(error: LearnLabError, secrets: set[str] | None = None) -> None:
    message = redact(str(error), secrets or set())
    typer.echo(f"Error: {message}")
    input_error = isinstance(error, (ConfigurationError, CurriculumError))
    raise typer.Exit(code=2 if input_error else 3) from None
