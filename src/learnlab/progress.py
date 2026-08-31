"""Safe, provider-neutral lifecycle progress events."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ProgressKind(StrEnum):
    """The stable lifecycle stages suitable for learner-facing rendering."""

    ENVIRONMENT_REQUESTED = "environment-requested"
    ALLOCATING_VMID = "allocating-vmid"
    CLONE_REQUESTED = "clone-requested"
    CLONE_WAITING = "clone-waiting"
    CLONE_COMPLETE = "clone-complete"
    START_REQUESTED = "start-requested"
    START_WAITING = "start-waiting"
    GUEST_AGENT_WAITING = "guest-agent-waiting"
    ADDRESS_DISCOVERY = "address-discovery"
    ENVIRONMENT_READY = "environment-ready"


@dataclass(frozen=True)
class ProgressEvent:
    """One safe, immutable update emitted during environment provisioning."""

    kind: ProgressKind
    message: str
    elapsed_seconds: float
    vmid: int | None = None
    attempt: int | None = None

    def __post_init__(self) -> None:
        if self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be nonnegative")
        if self.vmid is not None and self.vmid <= 0:
            raise ValueError("vmid must be positive when provided")
        if self.attempt is not None and self.attempt <= 0:
            raise ValueError("attempt must be positive when provided")


class ProgressObserver(Protocol):
    """Receives safe lifecycle progress updates."""

    def on_progress(self, event: ProgressEvent) -> None: ...


class NullProgressObserver:
    """Default observer that deliberately ignores lifecycle progress."""

    def on_progress(self, event: ProgressEvent) -> None:
        return None
