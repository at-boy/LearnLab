from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from learnlab.config import ProxmoxProfile
from learnlab.ssh import SshCommandTimeout, SshExecutor
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
