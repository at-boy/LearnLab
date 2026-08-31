from __future__ import annotations

from io import StringIO

import pytest

from learnlab.cli import TerminalProgressRenderer
from learnlab.progress import ProgressEvent, ProgressKind


def progress_event(
    kind: ProgressKind,
    message: str,
    elapsed_seconds: float,
    *,
    attempt: int | None = None,
) -> ProgressEvent:
    return ProgressEvent(
        kind=kind,
        message=message,
        elapsed_seconds=elapsed_seconds,
        attempt=attempt,
    )


def test_non_tty_progress_emits_deterministic_stage_and_heartbeat_lines() -> None:
    output = StringIO()
    renderer = TerminalProgressRenderer(output, is_terminal=False)

    renderer.on_progress(
        progress_event(
            ProgressKind.ENVIRONMENT_REQUESTED,
            "Creating lesson environment",
            0,
        )
    )
    renderer.on_progress(
        progress_event(
            ProgressKind.CLONE_WAITING,
            "Waiting for environment clone",
            2.75,
            attempt=3,
        )
    )
    renderer.close()

    assert output.getvalue() == (
        "Creating lesson environment\nWaiting for environment clone (attempt 3)\n"
    )


def test_tty_progress_updates_one_spinner_line_with_event_elapsed_time() -> None:
    output = StringIO()
    times = iter((0.0, 0.1))
    renderer = TerminalProgressRenderer(
        output,
        is_terminal=True,
        clock=lambda: next(times),
    )

    renderer.on_progress(
        progress_event(
            ProgressKind.ENVIRONMENT_REQUESTED,
            "Creating lesson environment",
            0,
        )
    )
    renderer.on_progress(
        progress_event(
            ProgressKind.CLONE_WAITING,
            "Waiting for environment clone",
            1.25,
            attempt=2,
        )
    )
    renderer.close()

    assert output.getvalue() == (
        "\r⠋ Creating lesson environment [0.0s]"
        "\r⠙ Waiting for environment clone (attempt 2) [1.2s]"
        "\n"
    )


def test_progress_renderer_closes_once_on_success() -> None:
    output = StringIO()
    renderer = TerminalProgressRenderer(
        output,
        is_terminal=True,
        clock=lambda: 0,
    )

    renderer.on_progress(
        progress_event(
            ProgressKind.ENVIRONMENT_READY,
            "Environment is ready",
            4,
        )
    )
    renderer.close()

    assert output.getvalue() == "\r⠋ Environment is ready [4.0s]\n"


@pytest.mark.parametrize("error", [RuntimeError("failed"), KeyboardInterrupt()])
def test_progress_renderer_context_closes_tty_line_on_error_or_interrupt(
    error: BaseException,
) -> None:
    output = StringIO()

    with pytest.raises(type(error)):
        with TerminalProgressRenderer(
            output,
            is_terminal=True,
            clock=lambda: 0,
        ) as renderer:
            renderer.on_progress(
                progress_event(
                    ProgressKind.ENVIRONMENT_REQUESTED,
                    "Creating lesson environment",
                    0,
                )
            )
            raise error

    assert output.getvalue().endswith("\n")
    assert output.getvalue().count("\n") == 1
