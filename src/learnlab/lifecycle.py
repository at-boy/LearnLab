"""Provider-neutral disposable-environment lifecycle orchestration."""

from __future__ import annotations

import re
import shutil
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from learnlab.curriculum import Course, Lesson
from learnlab.errors import LearnLabError, redact
from learnlab.providers.base import Provider
from learnlab.ssh import create_known_hosts, render_ssh_command
from learnlab.state import (
    EnvironmentPhase,
    EnvironmentRecord,
    StateConflictError,
    StateStore,
)

_TASK_TIMEOUT_SECONDS = 300.0
_GUEST_TIMEOUT_SECONDS = 300.0
_ERROR_SUMMARY_LIMIT = 500


class LifecycleError(LearnLabError):
    """Raised when lifecycle orchestration cannot safely complete."""


class StartProfile(Protocol):
    """Provider-profile metadata needed by the start lifecycle."""

    @property
    def name(self) -> str: ...

    @property
    def node(self) -> str: ...

    @property
    def ssh_user(self) -> str: ...

    @property
    def ssh_identity_file(self) -> Path: ...


@dataclass(frozen=True)
class StartRequest:
    """A selected course lesson and resolved provider profile."""

    course: Course
    lesson: Lesson
    profile: StartProfile
    provider_type: str


@dataclass(frozen=True)
class StartedEnvironment:
    """Connection details for a successfully started environment."""

    environment_id: str
    ip_address: str
    known_hosts: Path
    ssh_command: str


@dataclass(frozen=True)
class DestroySummary:
    """Environment IDs removed locally or retained after cleanup failures."""

    destroyed: list[str]
    failed: list[str]


class LifecycleService:
    """Coordinate provider calls with immediately durable local state."""

    def __init__(
        self,
        store: StateStore,
        provider: Provider | Mapping[str, Provider | Exception],
        state_root: Path,
        *,
        secrets: set[str] | None = None,
    ) -> None:
        self._store = store
        self._provider = provider
        self._state_root = state_root
        self._secrets = secrets or set()

    def start(self, request: StartRequest) -> StartedEnvironment:
        """Create and start one disposable environment for the selected lesson."""
        if (
            self._store.active_environment(
                request.course.collection_id, request.course.id
            )
            is not None
        ):
            raise StateConflictError(
                "Course already has an environment; run learnlab destroy first"
            )

        attempt = self._store.create_attempt(
            request.course.collection_id,
            request.course.id,
            request.lesson.id,
        )
        environment_id = str(uuid.uuid4())
        self._store.create_environment(
            EnvironmentRecord(
                id=environment_id,
                collection_id=request.course.collection_id,
                course_id=request.course.id,
                lesson_id=request.lesson.id,
                attempt_id=attempt.id,
                profile_name=request.profile.name,
                provider_type=request.provider_type,
                phase=EnvironmentPhase.ALLOCATING,
            )
        )

        provider = self._provider_for_profile(request.profile.name)
        try:
            vmid = provider.allocate_vmid()
            self._store.transition_environment(
                environment_id, EnvironmentPhase.ALLOCATING, vmid=vmid
            )
            clone_upid = provider.clone(vmid, _vm_name(request.course.id, vmid))
            self._store.transition_environment(
                environment_id,
                EnvironmentPhase.CLONING,
                vmid=vmid,
                upid=clone_upid,
            )
            provider.wait_for_task(
                request.profile.node, clone_upid, _TASK_TIMEOUT_SECONDS
            )
            location = provider.locate_vm(vmid)
            if location is None:
                raise LifecycleError(f"Provider could not locate cloned VM {vmid}")
            self._store.transition_environment(
                environment_id, EnvironmentPhase.STOPPED, node=location.node
            )

            start_upid = provider.start(vmid, location.node)
            self._store.transition_environment(
                environment_id, EnvironmentPhase.STARTING, upid=start_upid
            )
            provider.wait_for_task(location.node, start_upid, _TASK_TIMEOUT_SECONDS)
            self._store.transition_environment(environment_id, EnvironmentPhase.RUNNING)
            ip_address = provider.wait_for_ipv4(
                vmid, location.node, _GUEST_TIMEOUT_SECONDS
            )
            self._store.transition_environment(
                environment_id, EnvironmentPhase.RUNNING, ip_address=ip_address
            )

            known_hosts = create_known_hosts(self._state_root, environment_id)
            return StartedEnvironment(
                environment_id=environment_id,
                ip_address=ip_address,
                known_hosts=known_hosts,
                ssh_command=render_ssh_command(
                    request.profile, ip_address, known_hosts
                ),
            )
        except Exception as error:
            summary = _safe_error_summary(error, self._secrets)
            self._store.transition_environment(
                environment_id,
                EnvironmentPhase.FAILED,
                error_summary=summary,
            )
            raise LifecycleError(
                "Environment startup failed; retained partial state. "
                "Run learnlab destroy to clean it up."
            ) from None

    def destroy_all(
        self,
        preserve_completed: bool,
        confirmed_environments: tuple[EnvironmentRecord, ...],
    ) -> DestroySummary:
        """Destroy the confirmed environment snapshot, then clear transient state."""
        destroyed: list[str] = []
        failed: list[str] = []

        for environment in confirmed_environments:
            try:
                self._destroy_environment(environment)
            except Exception as error:
                self._store.transition_environment(
                    environment.id,
                    EnvironmentPhase.FAILED,
                    error_summary=_safe_error_summary(error, self._secrets),
                )
                failed.append(environment.id)
            else:
                destroyed.append(environment.id)

        if not self._store.list_environments():
            self._store.erase_all(preserve_completed)
        return DestroySummary(destroyed=destroyed, failed=failed)

    def _destroy_environment(self, environment: EnvironmentRecord) -> None:
        if environment.vmid is None:
            self._remove_local_environment(environment.id)
            return

        provider = self._provider_for_profile(environment.profile_name)
        location = provider.locate_vm(environment.vmid)
        if location is None:
            self._remove_local_environment(environment.id)
            return

        if location.status == "running":
            self._store.transition_environment(
                environment.id,
                EnvironmentPhase.STOPPING,
                node=location.node,
            )
            stop_upid = provider.stop(environment.vmid, location.node)
            self._store.transition_environment(
                environment.id,
                EnvironmentPhase.STOPPING,
                upid=stop_upid,
            )
            provider.wait_for_task(location.node, stop_upid, _TASK_TIMEOUT_SECONDS)

        self._store.transition_environment(
            environment.id,
            EnvironmentPhase.DELETING,
            node=location.node,
        )
        delete_upid = provider.delete(environment.vmid, location.node)
        self._store.transition_environment(
            environment.id,
            EnvironmentPhase.DELETING,
            upid=delete_upid,
        )
        provider.wait_for_task(location.node, delete_upid, _TASK_TIMEOUT_SECONDS)
        if provider.locate_vm(environment.vmid) is not None:
            raise LifecycleError(
                f"Provider still reports VM {environment.vmid} after deletion"
            )
        self._remove_local_environment(environment.id)

    def _remove_local_environment(self, environment_id: str) -> None:
        if (
            not environment_id
            or Path(environment_id).name != environment_id
            or environment_id in {".", ".."}
        ):
            raise LifecycleError("Unsafe environment identifier in local state")
        environment_dir = self._state_root / "environments" / environment_id
        if environment_dir.exists():
            shutil.rmtree(environment_dir)
        self._store.delete_environment(environment_id)

    def _provider_for_profile(self, profile_name: str) -> Provider:
        if not isinstance(self._provider, Mapping):
            return self._provider
        try:
            provider = self._provider[profile_name]
        except KeyError:
            raise LifecycleError(
                f"No provider available for recorded profile {profile_name}"
            ) from None
        if isinstance(provider, Exception):
            raise provider
        return provider


def _vm_name(course_id: str, vmid: int) -> str:
    normalized_course = re.sub(r"[^a-z0-9]+", "-", course_id.lower()).strip("-")
    suffix = f"-{vmid}"
    available = 63 - len("learnlab-") - len(suffix)
    bounded_course = normalized_course[:available].rstrip("-")
    return f"learnlab-{bounded_course}{suffix}"


def _safe_error_summary(error: Exception, secrets: set[str]) -> str:
    summary = redact(str(error), secrets)
    if not summary:
        summary = type(error).__name__
    if len(summary) > _ERROR_SUMMARY_LIMIT:
        summary = f"{summary[: _ERROR_SUMMARY_LIMIT - 3]}..."
    return summary
