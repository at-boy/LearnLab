"""Per-environment SSH host-key isolation and command rendering."""

from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import ipaddress
import os
import shlex
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Protocol, cast

from learnlab.errors import LearnLabError, redact

_CONNECT_TIMEOUT_SECONDS = 10
_MAX_CAPTURED_OUTPUT_BYTES = 8 * 1024
_MAX_HOST_KEY_SCAN_BYTES = 64 * 1024
_PROCESS_TERMINATION_GRACE_SECONDS = 1.0
_PROCESS_READER_JOIN_GRACE_SECONDS = 0.5
_PROCESS_READ_CHUNK_BYTES = 64 * 1024
_REDACTION_MARKER = "[REDACTED]"

ProcessFactory = Callable[..., subprocess.Popen[bytes]]


@dataclass(frozen=True)
class RemoteCommandResult:
    """The bounded, safe result of one remote curriculum command."""

    exit_code: int
    stdout: str
    stderr: str


class SshCommandTimeout(LearnLabError):
    """Raised when a remote verification command exceeds its deadline."""


class SshHostKeyError(LearnLabError):
    """Raised when an isolated SSH host key cannot be safely enrolled."""


@dataclass(frozen=True)
class HostKeyPresentation:
    """The target and key identities that require explicit learner trust."""

    target: str
    identities: tuple[tuple[str, str], ...]
    connection_command: str


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
        process_factory: ProcessFactory | None = None,
        secrets: set[str] | None = None,
    ) -> None:
        if runner is not None and process_factory is not None:
            raise ValueError("Use runner or process_factory, not both")
        self._state_root = state_root
        self._runner = runner
        self._process_factory = (
            process_factory
            if process_factory is not None
            else cast(ProcessFactory, subprocess.Popen)
        )
        self._secrets = secrets if secrets is not None else set()

    def enroll_host_key(
        self,
        profile: SshProfile,
        environment: RemoteEnvironment,
        confirm: Callable[[HostKeyPresentation], bool],
    ) -> bool:
        """Confirm and pin a stable presented key in one isolated environment."""
        known_hosts = _isolated_known_hosts_path(self._state_root, environment.id)
        if environment.ip_address is None:
            raise ValueError("Remote environment does not have an IP address")
        if known_hosts.is_symlink():
            raise SshHostKeyError("Refusing a non-isolated SSH host-key file")
        if known_hosts.exists() and known_hosts.stat().st_size > 0:
            known_hosts.chmod(0o600)
            return False

        known_hosts = create_known_hosts(self._state_root, environment.id)
        first_lines, first_identities = self._scan_host_keys(environment.ip_address)
        presentation = HostKeyPresentation(
            target=f"{profile.ssh_user}@{environment.ip_address}",
            identities=first_identities,
            connection_command=render_ssh_command(
                profile, environment.ip_address, known_hosts
            ),
        )
        if not confirm(presentation):
            raise SshHostKeyError("SSH host-key enrollment was declined")

        second_lines, second_identities = self._scan_host_keys(environment.ip_address)
        if second_lines != first_lines or second_identities != first_identities:
            raise SshHostKeyError("Presented SSH host key changed during confirmation")
        _replace_private_file(
            known_hosts, "".join(f"{line}\n" for line in second_lines)
        )
        return True

    def _scan_host_keys(
        self, target: str
    ) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
        """Acquire public keys without consulting or changing user SSH state."""
        try:
            ipaddress.ip_address(target)
        except ValueError:
            raise SshHostKeyError(
                "Environment SSH target is not an IP address"
            ) from None
        argv = [
            "ssh-keyscan",
            "-T",
            str(_CONNECT_TIMEOUT_SECONDS),
            "-t",
            "ed25519,ecdsa,rsa",
            target,
        ]
        try:
            completed = self._execute(
                argv,
                _CONNECT_TIMEOUT_SECONDS + 2,
                capture_limit=_MAX_HOST_KEY_SCAN_BYTES,
            )
        except subprocess.TimeoutExpired:
            raise SshHostKeyError("Timed out acquiring the SSH host key") from None
        if completed.returncode != 0:
            raise SshHostKeyError("Unable to acquire the SSH host key")
        return _parse_scanned_host_keys(completed.stdout, target)

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
            completed = self._execute(argv, timeout)
        except subprocess.TimeoutExpired as error:
            raise SshCommandTimeout(
                f"Remote command timed out after {error.timeout} seconds"
            ) from None

        return RemoteCommandResult(
            exit_code=completed.returncode,
            stdout=_safe_output(completed.stdout, self._secrets),
            stderr=_safe_output(completed.stderr, self._secrets),
        )

    def _execute(
        self,
        argv: list[str],
        timeout: float,
        *,
        capture_limit: int = _MAX_CAPTURED_OUTPUT_BYTES,
    ) -> subprocess.CompletedProcess[bytes]:
        """Run through the bounded production path or an isolated test runner."""
        if self._runner is not None:
            completed = self._runner(
                argv,
                capture_output=True,
                text=False,
                timeout=timeout,
                check=False,
            )
            return subprocess.CompletedProcess(
                argv,
                completed.returncode,
                (completed.stdout or b"")[:capture_limit],
                (completed.stderr or b"")[:capture_limit],
            )
        return _run_bounded_process(
            self._process_factory,
            argv,
            timeout,
            capture_limit,
        )


def _run_bounded_process(
    process_factory: ProcessFactory,
    argv: list[str],
    timeout: float,
    capture_limit: int,
) -> subprocess.CompletedProcess[bytes]:
    """Drain both pipes fully while retaining only a fixed prefix of each."""
    process = process_factory(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        start_new_session=True,
    )
    if process.stdout is None or process.stderr is None:
        streams = tuple(
            stream for stream in (process.stdout, process.stderr) if stream is not None
        )
        _cleanup_process(process, (), streams)
        raise LearnLabError("SSH process did not expose captured output")

    streams = (process.stdout, process.stderr)
    stdout = bytearray()
    stderr = bytearray()
    drain_errors: list[BaseException] = []
    readers = (
        threading.Thread(
            target=_drain_stream,
            args=(process.stdout, stdout, capture_limit, drain_errors),
            daemon=True,
        ),
        threading.Thread(
            target=_drain_stream,
            args=(process.stderr, stderr, capture_limit, drain_errors),
            daemon=True,
        ),
    )
    started_readers: list[threading.Thread] = []
    try:
        for reader in readers:
            reader.start()
            started_readers.append(reader)
        return_code = process.wait(timeout=timeout)
    except BaseException:
        _cleanup_process(process, tuple(started_readers), streams)
        raise

    try:
        readers_finished = _join_readers_bounded(tuple(started_readers))
    except BaseException:
        _cleanup_process(process, tuple(started_readers), streams)
        raise
    if not readers_finished:
        _cleanup_process(process, tuple(started_readers), streams)
        raise LearnLabError("SSH output streams did not close")
    _close_streams(streams)

    if drain_errors:
        error = drain_errors[0]
        raise LearnLabError(f"Unable to capture SSH output: {type(error).__name__}")
    return subprocess.CompletedProcess(argv, return_code, bytes(stdout), bytes(stderr))


def _drain_stream(
    stream: IO[bytes],
    captured: bytearray,
    capture_limit: int,
    errors: list[BaseException],
) -> None:
    try:
        while chunk := stream.read(_PROCESS_READ_CHUNK_BYTES):
            remaining = capture_limit - len(captured)
            if remaining > 0:
                captured.extend(chunk[:remaining])
    except BaseException as error:
        errors.append(error)


def _cleanup_process(
    process: subprocess.Popen[bytes],
    readers: tuple[threading.Thread, ...],
    streams: tuple[IO[bytes], ...],
) -> None:
    """Best-effort bounded cleanup that preserves the original exception."""
    forced_kill = False
    with contextlib.suppress(BaseException):
        _, forced_kill = _terminate_and_reap(process)

    if not forced_kill:
        readers_finished = False
        with contextlib.suppress(BaseException):
            readers_finished = _join_readers_bounded(readers)
        if not readers_finished:
            with contextlib.suppress(BaseException):
                _kill_group_and_reap(process)

    _close_streams(streams)
    with contextlib.suppress(BaseException):
        _join_readers_bounded(readers)


def _join_readers_bounded(readers: tuple[threading.Thread, ...]) -> bool:
    """Wait only a fixed grace period for all output drain threads."""
    deadline = time.monotonic() + _PROCESS_READER_JOIN_GRACE_SECONDS
    for reader in readers:
        reader.join(timeout=max(0.0, deadline - time.monotonic()))
    return all(not reader.is_alive() for reader in readers)


def _close_streams(streams: tuple[IO[bytes], ...]) -> None:
    """Close captured pipes so inherited writer descriptors cannot block return."""
    for stream in streams:
        with contextlib.suppress(BaseException):
            stream.close()


def _terminate_and_reap(
    process: subprocess.Popen[bytes],
) -> tuple[int, bool]:
    """Terminate the SSH process group, escalate after a grace, and reap."""
    _signal_process_group(process, signal.SIGTERM)
    try:
        return process.wait(timeout=_PROCESS_TERMINATION_GRACE_SECONDS), False
    except subprocess.TimeoutExpired:
        return _kill_group_and_reap(process), True


def _kill_group_and_reap(process: subprocess.Popen[bytes]) -> int:
    """Kill the SSH process group and reap its leader within a bounded grace."""
    _signal_process_group(process, signal.SIGKILL)
    return process.wait(timeout=_PROCESS_TERMINATION_GRACE_SECONDS)


def _signal_process_group(
    process: subprocess.Popen[bytes], sent_signal: signal.Signals
) -> None:
    """Signal the POSIX session created for SSH, with a portable leader fallback."""
    pid = getattr(process, "pid", None)
    killpg = getattr(os, "killpg", None)
    if os.name == "posix" and isinstance(pid, int) and callable(killpg):
        try:
            killpg(pid, sent_signal)
        except ProcessLookupError:
            return
        except OSError:
            pass
        else:
            return

    action = process.terminate if sent_signal is signal.SIGTERM else process.kill
    try:
        action()
    except ProcessLookupError:
        pass


def _safe_output(output: bytes, secrets: set[str]) -> str:
    """Decode, redact, and byte-bound captured SSH output."""
    decoded = output.decode("utf-8", errors="replace")
    partial_secret_start = _partial_secret_start(decoded, secrets)
    redacted = (
        redact(decoded, secrets)
        if partial_secret_start is None
        else redact(decoded[:partial_secret_start], secrets) + _REDACTION_MARKER
    )
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


def _partial_secret_start(text: str, secrets: set[str]) -> int | None:
    """Find a captured suffix that is only the beginning of a configured secret."""
    starts: list[int] = []
    for secret in secrets:
        maximum = min(len(text), len(secret) - 1)
        for length in range(maximum, 0, -1):
            if text.endswith(secret[:length]):
                starts.append(len(text) - length)
                break
    return min(starts) if starts else None


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
    known_hosts = _isolated_known_hosts_path(state_root, environment_id)
    environment_dir = known_hosts.parent
    environments_dir = environment_dir.parent
    environments_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if environments_dir.is_symlink() or not environments_dir.is_dir():
        raise SshHostKeyError("Refusing a non-isolated SSH environments directory")
    environment_dir.mkdir(exist_ok=True, mode=0o700)
    if environment_dir.is_symlink() or not environment_dir.is_dir():
        raise SshHostKeyError("Refusing a non-isolated SSH environment directory")
    environment_dir.chmod(0o700)
    if known_hosts.is_symlink():
        raise SshHostKeyError("Refusing a non-isolated SSH host-key file")
    descriptor = os.open(
        known_hosts,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    os.fchmod(descriptor, 0o600)
    os.close(descriptor)
    return known_hosts


def _parse_scanned_host_keys(
    output: bytes, target: str
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """Validate keyscan output and derive OpenSSH-style SHA256 identities."""
    try:
        decoded = output.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise SshHostKeyError("SSH host-key scan returned invalid key data") from None

    records: list[tuple[str, str, bytes]] = []
    seen_records: set[tuple[str, str]] = set()
    keys_by_algorithm: dict[str, str] = {}
    expected_hosts = {target, f"[{target}]:22"}
    for raw_line in decoded.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 3 or parts[0] not in expected_hosts:
            raise SshHostKeyError("SSH host-key scan returned an unexpected target")
        algorithm, encoded_key = parts[1], parts[2]
        if not algorithm.startswith(("ssh-", "ecdsa-")):
            raise SshHostKeyError("SSH host-key scan returned an unsupported key")
        try:
            key_blob = base64.b64decode(encoded_key, validate=True)
        except (binascii.Error, ValueError):
            raise SshHostKeyError("SSH host-key scan returned an invalid key") from None

        record = (algorithm, encoded_key)
        if record in seen_records:
            raise SshHostKeyError("SSH host-key scan returned a duplicate key")
        if algorithm in keys_by_algorithm:
            raise SshHostKeyError(
                "SSH host-key scan returned conflicting keys for one algorithm"
            )
        seen_records.add(record)
        keys_by_algorithm[algorithm] = encoded_key
        records.append((algorithm, encoded_key, key_blob))
    if not records:
        raise SshHostKeyError("SSH host-key scan returned no keys")

    lines: list[str] = []
    identities: list[tuple[str, str]] = []
    for algorithm, encoded_key, key_blob in sorted(records):
        fingerprint = base64.b64encode(hashlib.sha256(key_blob).digest()).decode()
        lines.append(f"{target} {algorithm} {encoded_key}")
        identities.append((algorithm, f"SHA256:{fingerprint.rstrip('=')}"))
    return tuple(lines), tuple(identities)


def _replace_private_file(path: Path, content: str) -> None:
    """Atomically replace one isolated host-key file with private permissions."""
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".known_hosts-", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        temporary_path.replace(path)
        path.chmod(0o600)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise


def render_ssh_command(profile: SshProfile, ip: str, known_hosts: Path) -> str:
    """Render a shell-safe SSH command using only the isolated host-key file."""
    return shlex.join(
        [
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
            f"{profile.ssh_user}@{ip}",
        ]
    )
