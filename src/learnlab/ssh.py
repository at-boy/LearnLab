"""Per-environment SSH host-key isolation and command rendering."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Protocol


class SshProfile(Protocol):
    """The profile fields needed to render an SSH command."""

    @property
    def ssh_user(self) -> str: ...

    @property
    def ssh_identity_file(self) -> Path: ...


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


def render_ssh_command(
    profile: SshProfile, ip: str, known_hosts: Path
) -> str:
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
