from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from learnlab.config import ProxmoxProfile
from learnlab.errors import ProviderError
from learnlab.providers.base import ProviderHealth, VmLocation
from learnlab.state import StateStore


class RecordingProvider:
    """Behavioral provider fake that records completed boundary calls."""

    def __init__(self) -> None:
        self.operations: list[str] = []
        self.clone_names: list[str] = []
        self._failures: dict[str, ProviderError] = {}
        self.api_origin = "https://proxmox.example.test:8006"
        self.profile_fingerprint = "test-provider-fingerprint"

    def fail_on(self, operation: str, error: ProviderError) -> None:
        self._failures[operation] = error

    def _record(self, operation: str) -> None:
        self.operations.append(operation)
        if error := self._failures.get(operation):
            raise error

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(())

    def allocate_vmid(self) -> int:
        self._record("allocate_vmid")
        return 102

    def clone(self, vmid: int, name: str) -> str:
        self._record(f"clone:{vmid}")
        self.clone_names.append(name)
        return "clone"

    def wait_for_task(
        self,
        node: str,
        upid: str,
        timeout: float,
        heartbeat: Callable[[int], None] | None = None,
    ) -> None:
        self._record(f"wait:{upid}")

    def locate_vm(self, vmid: int) -> VmLocation | None:
        self._record(f"locate:{vmid}")
        return VmLocation(
            node="pve02",
            status="stopped",
            name=self.clone_names[-1],
        )

    def start(self, vmid: int, node: str) -> str:
        self._record(f"start:{vmid}")
        return "start"

    def stop(self, vmid: int, node: str) -> str:
        self._record(f"stop:{vmid}")
        return "stop"

    def wait_for_ipv4(
        self,
        vmid: int,
        node: str,
        timeout: float,
        heartbeat: Callable[[int], None] | None = None,
    ) -> str:
        self._record(f"wait_for_ipv4:{vmid}")
        return "192.0.2.10"

    def delete(self, vmid: int, node: str) -> str:
        self._record(f"delete:{vmid}")
        return "delete"


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state_store = StateStore(tmp_path / "learnlab.db")
    state_store.initialize()
    return state_store


@pytest.fixture
def recording_provider() -> RecordingProvider:
    return RecordingProvider()


@pytest.fixture
def failing_provider() -> RecordingProvider:
    return RecordingProvider()


@pytest.fixture
def profile_fixture() -> Callable[..., ProxmoxProfile]:
    def build_profile(**overrides: object) -> ProxmoxProfile:
        values: dict[str, object] = {
            "name": "home-proxmox",
            "api_url": "https://proxmox.example.test:8006",
            "token_id": "learnlab@pam!automation",
            "token_secret_env": "LEARNLAB_TEST_SECRET",
            "template_vmid": 9001,
            "template_name": "debian-12-learning",
            "node": "pve",
            "storage": "local-lvm",
            "network": "vmbr0",
            "ssh_user": "student",
            "ssh_identity_file": "~/.ssh/learning-platform",
            "tls_verify": True,
        }
        values.update(overrides)
        return ProxmoxProfile(**values)  # type: ignore[arg-type]

    return build_profile
