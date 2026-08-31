from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderCheck:
    """One human-readable provider prerequisite result."""

    name: str
    ok: bool
    detail: str
    required: bool = True


@dataclass(frozen=True)
class ProviderHealth:
    """Read-only health validation results for a provider."""

    checks: tuple[ProviderCheck, ...]
    warnings: tuple[str, ...] = ()
    provider_error: bool = False


@dataclass(frozen=True)
class VmLocation:
    """The discovered location and lifecycle state of a virtual machine."""

    node: str
    status: str
    name: str


class Provider(Protocol):
    """The provider operations required by LearnLab lifecycle services."""

    @property
    def api_origin(self) -> str: ...

    @property
    def profile_fingerprint(self) -> str: ...

    def health_check(self) -> ProviderHealth: ...

    def allocate_vmid(self) -> int: ...

    def clone(self, vmid: int, name: str) -> str: ...

    def wait_for_task(
        self,
        node: str,
        upid: str,
        timeout: float,
        heartbeat: Callable[[int], None] | None = None,
    ) -> None: ...

    def locate_vm(self, vmid: int) -> VmLocation | None: ...

    def start(self, vmid: int, node: str) -> str: ...

    def stop(self, vmid: int, node: str) -> str: ...

    def wait_for_ipv4(
        self,
        vmid: int,
        node: str,
        timeout: float,
        heartbeat: Callable[[int], None] | None = None,
        guest_agent_heartbeat: Callable[[int], None] | None = None,
        address_heartbeat: Callable[[int], None] | None = None,
    ) -> str: ...

    def delete(self, vmid: int, node: str) -> str: ...
