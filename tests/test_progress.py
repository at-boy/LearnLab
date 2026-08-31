from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from learnlab.progress import NullProgressObserver, ProgressEvent, ProgressKind


def test_progress_event_is_immutable_and_validates_timing_fields() -> None:
    event = ProgressEvent(
        kind=ProgressKind.CLONE_WAITING,
        message="Waiting for the environment clone",
        elapsed_seconds=2.5,
        vmid=102,
        attempt=1,
    )

    assert event.kind.value == "clone-waiting"
    with pytest.raises(FrozenInstanceError):
        event.message = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="elapsed_seconds"):
        ProgressEvent(ProgressKind.CLONE_WAITING, "Waiting", -0.1)
    with pytest.raises(ValueError, match="attempt"):
        ProgressEvent(ProgressKind.CLONE_WAITING, "Waiting", 0, attempt=0)


def test_null_progress_observer_accepts_events() -> None:
    NullProgressObserver().on_progress(
        ProgressEvent(ProgressKind.ENVIRONMENT_REQUESTED, "Creating environment", 0)
    )
