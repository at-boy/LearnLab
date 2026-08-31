"""Per-environment SSH host-key isolation and command rendering."""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from learnlab.errors import LearnLabError, redact

_CONNECT_TIMEOUT_SECONDS = 10
_MAX_CAPTURED_OUTPUT_BYTES = 8 * 1024
_REDACTION_MARKER = "[REDACTED]"


@dataclass(frozen=True)
class RemoteCommandResult:
    """The bounded, safe result of one remote curriculum command."""

    exit_code: int
    stdout: str
    stderr: str


class SshCommandTimeout(LearnLabError):
    """Raised when a remote verification command exceeds its deadline."""


class RemoteEnvironment(Protocol):
    """The environment fields needed to run a remote command."""

    @property
    def id(self) -> str: ...

    @property
    def ip_address(self) -> str | None: ...


class SshProfile(Protocol):
    """The profile fields needed to render an SSH command."""

    @property
    def ssh_user(self) -> str: ...

    @property
    def ssh_identity_file(self) -> Path: ...


class SshExecutor:
    """Execute one curriculum-authored command through strict SSH settings."""

    def __init__(
        self,
        state_root: Path,
        *,
        runner: Callable[..., subprocess.CompletedProcess[bytes]] | None = None,
        secrets: set[str] | None = None,
    ) -> None:
        self._state_root = state_root
        self._runner = (
            runner
            if runner is not None
            else cast(Callable[..., subprocess.CompletedProcess[bytes]], subprocess.run)
        )
        self._secrets = secrets or set()

    def run(
        self,
        profile: SshProfile,
        environment: RemoteEnvironment,
        command: str,
        timeout: float,
    ) -> RemoteCommandResult:
        """Run a single remote command without invoking a local shell."""
        known_hosts = _isolated_known_hosts_path(self._state_root, environment.id)
        if environment.ip_address is None:
            raise ValueError("Remote environment does not have an IP address")

        argv = [
            "ssh",
            "-i",
            str(profile.ssh_identity_file),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            "-o",
            "GlobalKnownHostsFile=/dev/null",
            "-o",
            f"ConnectTimeout={_CONNECT_TIMEOUT_SECONDS}",
            f"{profile.ssh_user}@{environment.ip_address}",
            command,
        ]
        try:
            completed = self._runner(
                argv,
                capture_output=True,
                text=False,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise SshCommandTimeout(
                f"Remote command timed out after {error.timeout} seconds"
            ) from None

        return RemoteCommandResult(
            exit_code=completed.returncode,
            stdout=_safe_output(completed.stdout, self._secrets),
            stderr=_safe_output(completed.stderr, self._secrets),
        )


def _safe_output(output: bytes, secrets: set[str]) -> str:
    """Decode, redact, and byte-bound captured SSH output."""
    redacted = redact(output.decode("utf-8", errors="replace"), secrets)
    encoded = redacted.encode("utf-8")
    if len(encoded) <= _MAX_CAPTURED_OUTPUT_BYTES:
        return redacted

    bounded = encoded[:_MAX_CAPTURED_OUTPUT_BYTES].decode("utf-8", errors="ignore")
    if bounded.endswith(_REDACTION_MARKER):
        return bounded
    marker_start = _partial_redaction_start(bounded)
    if marker_start is None:
        return bounded

    before_marker = bounded[:marker_start]
    while (
        len((before_marker + _REDACTION_MARKER).encode("utf-8"))
        > _MAX_CAPTURED_OUTPUT_BYTES
    ):
        before_marker = before_marker[:-1]
    return before_marker + _REDACTION_MARKER


def _partial_redaction_start(text: str) -> int | None:
    """Return a trailing partial redaction marker's starting index, if any."""
    for length in range(len(_REDACTION_MARKER) - 1, 0, -1):
        if text.endswith(_REDACTION_MARKER[:length]):
            return len(text) - length
    return None


def _isolated_known_hosts_path(state_root: Path, environment_id: str) -> Path:
    """Return the host-key path only for one safe environment path component."""
    if (
        not environment_id
        or Path(environment_id).name != environment_id
        or environment_id in {".", ".."}
    ):
        raise ValueError("Unsafe environment identifier")
    return state_root / "environments" / environment_id / "known_hosts"


def create_known_hosts(state_root: Path, environment_id: str) -> Path:
    """Create an empty, private host-key file for one environment."""
    environment_dir = state_root / "environments" / environment_id
    environment_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    environment_dir.chmod(0o700)
    known_hosts = environment_dir / "known_hosts"
    descriptor = os.open(
        known_hosts,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    os.close(descriptor)
    known_hosts.chmod(0o600)
    return known_hosts


def render_ssh_command(profile: SshProfile, ip: str, known_hosts: Path) -> str:
    """Render a shell-safe SSH command using only the isolated host-key file."""
    return shlex.join(
        [
            "ssh",
            "-i",
            str(profile.ssh_identity_file),
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            f"{profile.ssh_user}@{ip}",
        ]
    )
