from __future__ import annotations

import subprocess
from collections import deque
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from learnlab.config import ProxmoxProfile
from learnlab.ssh import (
    HostKeyPresentation,
    SshCommandTimeout,
    SshExecutor,
    SshHostKeyError,
    create_known_hosts,
)
from learnlab.state import EnvironmentPhase, EnvironmentRecord


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
        "ip_address": "192.0.2.10",
    }
    values.update(overrides)
    return EnvironmentRecord(**values)  # type: ignore[arg-type]


def recording_runner(
    captured: dict[str, Any],
    completed: subprocess.CompletedProcess[bytes],
) -> Callable[..., subprocess.CompletedProcess[bytes]]:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return completed

    return run


def private_value() -> str:
    return "-".join(("private", "token"))


HOST_KEY = "192.0.2.10 ssh-ed25519 aG9zdC1wdWJsaWMta2V5"
CHANGED_HOST_KEY = "192.0.2.10 ssh-ed25519 Y2hhbmdlZC1ob3N0LWtleQ=="


def queued_runner(
    completed: list[subprocess.CompletedProcess[bytes]],
    captured: list[tuple[list[str], dict[str, Any]]],
) -> Callable[..., subprocess.CompletedProcess[bytes]]:
    results = deque(completed)

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        captured.append((argv, kwargs))
        return results.popleft()

    return run


class TrackingStream(BytesIO):
    def __init__(self, value: bytes) -> None:
        super().__init__(value)
        self.total_read = 0

    def read(self, size: int = -1) -> bytes:
        chunk = super().read(size)
        self.total_read += len(chunk)
        return chunk


class FakeProcess:
    def __init__(
        self,
        stdout: bytes,
        stderr: bytes,
        *,
        returncode: int = 0,
        time_out: bool = False,
        ignore_terminate: bool = False,
    ) -> None:
        self.stdout = TrackingStream(stdout)
        self.stderr = TrackingStream(stderr)
        self.returncode: int | None = None
        self._final_returncode = returncode
        self._time_out = time_out
        self._ignore_terminate = ignore_terminate
        self.terminated = False
        self.killed = False
        self.reaped = False
        self.wait_calls: list[float | None] = []

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        if self._time_out and not self.killed:
            if not self.terminated or self._ignore_terminate:
                raise subprocess.TimeoutExpired(["ssh"], timeout)
        self.returncode = self._final_returncode
        self.reaped = True
        return self._final_returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


def test_production_process_drains_large_both_streams_with_capped_capture(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    stdout = b"a" * (4 * 1024 * 1024)
    stderr = b"b" * (3 * 1024 * 1024)
    process = FakeProcess(stdout, stderr, returncode=23)
    captured: dict[str, Any] = {}

    def process_factory(argv: list[str], **kwargs: Any) -> FakeProcess:
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return process

    executor = SshExecutor(tmp_path, process_factory=process_factory)

    result = executor.run(profile_fixture(), make_environment(), "false", timeout=30)

    assert result.exit_code == 23
    assert result.stdout == "a" * 8192
    assert result.stderr == "b" * 8192
    assert process.stdout.total_read == len(stdout)
    assert process.stderr.total_read == len(stderr)
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["stdin"] is subprocess.DEVNULL
    assert captured["kwargs"]["stdout"] is subprocess.PIPE
    assert captured["kwargs"]["stderr"] is subprocess.PIPE
    assert captured["argv"][-1] == "false"


def test_production_timeout_terminates_kills_and_reaps_process(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    process = FakeProcess(
        b"partial stdout", b"partial stderr", time_out=True, ignore_terminate=True
    )
    executor = SshExecutor(
        tmp_path,
        process_factory=lambda argv, **kwargs: process,
    )

    with pytest.raises(SshCommandTimeout, match="0.01"):
        executor.run(
            profile_fixture(), make_environment(), "long-command", timeout=0.01
        )

    assert process.terminated is True
    assert process.killed is True
    assert process.reaped is True
    assert process.wait_calls[0] == 0.01


def test_confirms_presented_host_key_before_writing_and_then_uses_strict_ssh(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    known_hosts = create_known_hosts(tmp_path, "env-1")
    captured: list[tuple[list[str], dict[str, Any]]] = []
    presentations: list[HostKeyPresentation] = []
    runner = queued_runner(
        [
            subprocess.CompletedProcess([], 0, f"{HOST_KEY}\n".encode(), b""),
            subprocess.CompletedProcess([], 0, f"{HOST_KEY}\n".encode(), b""),
            subprocess.CompletedProcess([], 0, b"strict connection worked", b""),
        ],
        captured,
    )
    executor = SshExecutor(tmp_path, runner=runner)

    enrolled = executor.enroll_host_key(
        profile_fixture(),
        make_environment(),
        lambda presentation: presentations.append(presentation) or True,
    )
    result = executor.run(
        profile_fixture(), make_environment(), "test -r /etc/os-release", timeout=15
    )

    assert enrolled is True
    assert presentations == [
        HostKeyPresentation(
            target="student@192.0.2.10",
            identities=(
                (
                    "ssh-ed25519",
                    "SHA256:hXBw+k0I59jZzDV4ZC5NNDnXbG6HjQJobltlAdMlBms",
                ),
            ),
            connection_command=(
                "ssh -i '~/.ssh/learning-platform' -o BatchMode=yes -o "
                "StrictHostKeyChecking=yes -o "
                f"UserKnownHostsFile={known_hosts} -o "
                "GlobalKnownHostsFile=/dev/null student@192.0.2.10"
            ),
        )
    ]
    assert known_hosts.read_text(encoding="utf-8") == f"{HOST_KEY}\n"
    assert (known_hosts.stat().st_mode & 0o777) == 0o600
    assert result.exit_code == 0
    assert result.stdout == "strict connection worked"
    strict_argv, strict_kwargs = captured[-1]
    assert "StrictHostKeyChecking=yes" in strict_argv
    assert f"UserKnownHostsFile={known_hosts}" in strict_argv
    assert strict_kwargs.get("shell", False) is False


def test_declined_host_key_is_not_written(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    known_hosts = create_known_hosts(tmp_path, "env-1")
    executor = SshExecutor(
        tmp_path,
        runner=queued_runner(
            [subprocess.CompletedProcess([], 0, f"{HOST_KEY}\n".encode(), b"")],
            [],
        ),
    )

    with pytest.raises(SshHostKeyError, match="declined"):
        executor.enroll_host_key(
            profile_fixture(), make_environment(), lambda presentation: False
        )

    assert known_hosts.read_text(encoding="utf-8") == ""


def test_changed_host_key_after_confirmation_fails_closed_without_writing(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    known_hosts = create_known_hosts(tmp_path, "env-1")
    executor = SshExecutor(
        tmp_path,
        runner=queued_runner(
            [
                subprocess.CompletedProcess([], 0, f"{HOST_KEY}\n".encode(), b""),
                subprocess.CompletedProcess(
                    [], 0, f"{CHANGED_HOST_KEY}\n".encode(), b""
                ),
            ],
            [],
        ),
    )

    with pytest.raises(SshHostKeyError, match="changed"):
        executor.enroll_host_key(
            profile_fixture(), make_environment(), lambda presentation: True
        )

    assert known_hosts.read_text(encoding="utf-8") == ""


def test_host_key_enrollment_refuses_symlink_without_touching_its_target(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    state_root = tmp_path / "state"
    environment_dir = state_root / "environments" / "env-1"
    environment_dir.mkdir(parents=True)
    normal_known_hosts = tmp_path / "normal-known-hosts"
    normal_known_hosts.write_text("keep this key\n", encoding="utf-8")
    (environment_dir / "known_hosts").symlink_to(normal_known_hosts)
    executor = SshExecutor(
        state_root,
        runner=queued_runner(
            [subprocess.CompletedProcess([], 0, f"{HOST_KEY}\n".encode(), b"")],
            [],
        ),
    )

    with pytest.raises(SshHostKeyError, match="isolated"):
        executor.enroll_host_key(
            profile_fixture(), make_environment(), lambda presentation: True
        )

    assert normal_known_hosts.read_text(encoding="utf-8") == "keep this key\n"


def test_runs_one_strict_noninteractive_command_with_isolated_host_keys(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    captured: dict[str, Any] = {}
    command = "grep -q '^ID=nixos' /etc/os-release; echo $HOME"
    executor = SshExecutor(
        tmp_path,
        runner=recording_runner(
            captured, subprocess.CompletedProcess([], 0, b"verified", b"")
        ),
    )

    result = executor.run(profile_fixture(), make_environment(), command, timeout=15)

    known_hosts = tmp_path / "environments" / "env-1" / "known_hosts"
    assert result.exit_code == 0
    assert captured["argv"] == [
        "ssh",
        "-i",
        "~/.ssh/learning-platform",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=10",
        "student@192.0.2.10",
        command,
    ]
    assert captured["kwargs"] == {
        "capture_output": True,
        "text": False,
        "timeout": 15,
        "check": False,
    }
    assert captured["kwargs"].get("shell", False) is False
    assert "~/.ssh/known_hosts" not in captured["argv"]
    assert captured["argv"][-1] == command


def test_rejects_environment_ids_that_escape_isolated_known_hosts_directory(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    captured: dict[str, Any] = {}
    state_root = tmp_path / "state"
    escaping_id = "../../home/.ssh"
    normal_known_hosts = tmp_path / "home" / ".ssh" / "known_hosts"
    executor = SshExecutor(
        state_root,
        runner=recording_runner(captured, subprocess.CompletedProcess([], 0, b"", b"")),
    )

    with pytest.raises(ValueError, match="Unsafe environment identifier"):
        executor.run(
            profile_fixture(), make_environment(id=escaping_id), "true", timeout=30
        )

    assert not normal_known_hosts.exists()
    assert captured == {}


def test_preserves_nonzero_exit_status_and_decodes_binary_output(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    executor = SshExecutor(
        tmp_path,
        runner=recording_runner(
            {}, subprocess.CompletedProcess([], 17, b"stdout\xff", b"stderr\xfe")
        ),
    )

    result = executor.run(profile_fixture(), make_environment(), "false", timeout=30)

    assert result.exit_code == 17
    assert result.stdout == "stdout\ufffd"
    assert result.stderr == "stderr\ufffd"


def test_bounds_decoded_stdout_and_stderr_to_eight_kib_each(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    executor = SshExecutor(
        tmp_path,
        runner=recording_runner(
            {},
            subprocess.CompletedProcess([], 1, b"a" * 9000, "🙂".encode() * 3000),
        ),
    )

    result = executor.run(profile_fixture(), make_environment(), "false", timeout=30)

    assert result.stdout == "a" * 8192
    assert len(result.stderr.encode("utf-8")) <= 8192
    assert result.stderr.startswith("🙂")


def test_maps_subprocess_timeout_without_disclosing_command(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    command = f"test {private_value()} = {private_value()}"

    def times_out(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    executor = SshExecutor(tmp_path, runner=times_out)

    with pytest.raises(SshCommandTimeout) as error:
        executor.run(profile_fixture(), make_environment(), command, timeout=9)

    assert "9" in str(error.value)
    assert command not in str(error.value)


def test_redacts_configured_secrets_before_returning_bounded_output(
    tmp_path: Path, profile_fixture: Callable[..., ProxmoxProfile]
) -> None:
    configured_value = private_value()
    executor = SshExecutor(
        tmp_path,
        secrets={configured_value},
        runner=recording_runner(
            {},
            subprocess.CompletedProcess(
                [],
                1,
                ("x" * 8188 + configured_value).encode(),
                f"failure: {configured_value}".encode(),
            ),
        ),
    )

    result = executor.run(profile_fixture(), make_environment(), "false", timeout=30)

    assert configured_value not in result.stdout
    assert configured_value not in result.stderr
    assert result.stdout.endswith("[REDACTED]")
    assert result.stderr == "failure: [REDACTED]"
