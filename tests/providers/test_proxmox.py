from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import cast
from urllib.parse import parse_qs

import httpx
import pytest

from learnlab.config import ProxmoxProfile
from learnlab.errors import (
    ProviderAuthenticationError,
    ProviderOperationError,
    ProviderTaskFailed,
    ProviderTimeoutError,
)
from learnlab.providers.proxmox import ProxmoxProvider
from tests.providers.fake_proxmox import FakeProxmoxServer, fake_proxmox_server


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


@pytest.fixture
def fake_server() -> Iterator[FakeProxmoxServer]:
    with fake_proxmox_server() as server:
        yield server


@pytest.fixture
def profile(profile_fixture: Callable[..., ProxmoxProfile]) -> ProxmoxProfile:
    return profile_fixture(
        api_url="http://127.0.0.1:1",
        node="pve02",
        template_name="nixos-26.05-base-v2",
    )


def provider_for(
    fake_server: FakeProxmoxServer, profile: ProxmoxProfile
) -> ProxmoxProvider:
    client = httpx.Client(base_url=f"{fake_server.url}/api2/json", timeout=10.0)
    clock = FakeClock()
    return ProxmoxProvider(
        profile,
        "private-value",
        client=client,
        clock=clock.now,
        sleep=clock.sleep,
    )


def provider_with_clock(
    fake_server: FakeProxmoxServer, profile: ProxmoxProfile
) -> tuple[ProxmoxProvider, FakeClock]:
    clock = FakeClock()
    provider = ProxmoxProvider(
        profile,
        "private-value",
        client=httpx.Client(base_url=f"{fake_server.url}/api2/json", timeout=10.0),
        clock=clock.now,
        sleep=clock.sleep,
    )
    return provider, clock


@pytest.fixture
def provider(
    fake_server: FakeProxmoxServer, profile: ProxmoxProfile
) -> ProxmoxProvider:
    return provider_for(fake_server, profile)


def test_clone_uses_post_and_expected_form(
    fake_server: FakeProxmoxServer, profile: ProxmoxProfile
) -> None:
    fake_server.queue(200, {"data": "UPID:pve02:clone:"})

    upid = provider_for(fake_server, profile).clone(102, "learnlab-102")

    request = fake_server.requests.one()
    assert request.method == "POST"
    assert request.path == "/api2/json/nodes/pve02/qemu/9001/clone"
    assert parse_qs(request.body) == {
        "newid": ["102"],
        "name": ["learnlab-102"],
        "full": ["1"],
        "storage": ["local-lvm"],
    }
    assert request.authorization == "PVEAPIToken=learnlab@pam!automation=private-value"
    assert upid == "UPID:pve02:clone:"


@pytest.mark.parametrize(
    ("operation", "method", "path"),
    [
        ("start", "POST", "/api2/json/nodes/pve02/qemu/102/status/start"),
        ("stop", "POST", "/api2/json/nodes/pve02/qemu/102/status/stop"),
        ("delete", "DELETE", "/api2/json/nodes/pve02/qemu/102"),
    ],
)
def test_mutating_methods_are_explicit(
    operation: str,
    method: str,
    path: str,
    fake_server: FakeProxmoxServer,
    profile: ProxmoxProfile,
) -> None:
    fake_server.queue(200, {"data": "UPID:pve02:task:"})

    result = getattr(provider_for(fake_server, profile), operation)(102, "pve02")

    assert fake_server.requests.one().method == method
    assert fake_server.requests.one().path == path
    assert result == "UPID:pve02:task:"


def test_allocate_vmid_uses_cluster_nextid(
    fake_server: FakeProxmoxServer, provider: ProxmoxProvider
) -> None:
    fake_server.queue(200, {"data": "102"})

    assert provider.allocate_vmid() == 102
    assert fake_server.requests.one().method == "GET"
    assert fake_server.requests.one().path == "/api2/json/cluster/nextid"


def test_locate_vm_returns_its_node_and_status(
    fake_server: FakeProxmoxServer, provider: ProxmoxProvider
) -> None:
    fake_server.queue(
        200,
        {"data": [{"vmid": 102, "node": "pve03", "status": "stopped"}]},
    )

    location = provider.locate_vm(102)

    assert location is not None
    assert location.node == "pve03"
    assert location.status == "stopped"


def test_locate_vm_returns_none_when_the_vm_is_absent(
    fake_server: FakeProxmoxServer, provider: ProxmoxProvider
) -> None:
    fake_server.queue(200, {"data": []})

    assert provider.locate_vm(102) is None


def test_wait_for_task_requires_stopped_and_ok(
    fake_server: FakeProxmoxServer, provider: ProxmoxProvider
) -> None:
    fake_server.queue(200, {"data": {"status": "running"}})
    fake_server.queue(200, {"data": {"status": "stopped", "exitstatus": "OK"}})

    provider.wait_for_task("pve02", "UPID:pve02:a/b!:", timeout=5)

    assert fake_server.requests.last().path.endswith(
        "UPID%3Apve02%3Aa%2Fb%21%3A/status"
    )


def test_wait_for_task_rejects_non_ok_exit(
    fake_server: FakeProxmoxServer, provider: ProxmoxProvider
) -> None:
    fake_server.queue(200, {"data": {"status": "stopped", "exitstatus": "ERROR"}})

    with pytest.raises(ProviderTaskFailed, match="ERROR"):
        provider.wait_for_task("pve02", "UPID:pve02:bad:", timeout=5)


def test_wait_for_task_times_out_with_operation_context(
    fake_server: FakeProxmoxServer, provider: ProxmoxProvider
) -> None:
    fake_server.always(200, {"data": {"status": "running"}})

    with pytest.raises(ProviderTimeoutError, match="UPID"):
        provider.wait_for_task("pve02", "UPID:pve02:slow:", timeout=2)


def test_wait_for_task_rejects_success_after_a_short_deadline(
    fake_server: FakeProxmoxServer, profile: ProxmoxProfile
) -> None:
    fake_server.queue(200, {"data": {"status": "running"}})
    fake_server.queue(200, {"data": {"status": "stopped", "exitstatus": "OK"}})
    provider, clock = provider_with_clock(fake_server, profile)

    with pytest.raises(ProviderTimeoutError):
        provider.wait_for_task("pve02", "UPID:pve02:slow:", timeout=1)

    assert clock.value == 1
    assert len(fake_server.requests.all()) == 1


def test_wait_for_ipv4_ignores_loopback_and_invalid_addresses(
    fake_server: FakeProxmoxServer, provider: ProxmoxProvider
) -> None:
    fake_server.queue(500, {"errors": "guest agent unavailable"})
    fake_server.queue(200, {"data": {}})
    fake_server.queue(
        200,
        {
            "data": {
                "result": [
                    {
                        "name": "lo",
                        "ip-addresses": [
                            {
                                "ip-address": "127.0.0.1",
                                "ip-address-type": "ipv4",
                            }
                        ],
                    },
                    {
                        "name": "eth0",
                        "ip-addresses": [
                            {
                                "ip-address": "not-an-ip",
                                "ip-address-type": "ipv4",
                            },
                            {
                                "ip-address": "2001:db8::1",
                                "ip-address-type": "ipv6",
                            },
                            {
                                "ip-address": "192.0.2.10",
                                "ip-address-type": "ipv4",
                            },
                        ],
                    },
                ]
            }
        },
    )

    assert provider.wait_for_ipv4(102, "pve02", timeout=6) == "192.0.2.10"
    assert [request.method for request in fake_server.requests.all()] == [
        "POST",
        "POST",
        "GET",
    ]


def test_wait_for_ipv4_rejects_agent_readiness_after_a_short_deadline(
    fake_server: FakeProxmoxServer, profile: ProxmoxProfile
) -> None:
    fake_server.queue(500, {"errors": "guest agent unavailable"})
    fake_server.queue(200, {"data": {}})
    fake_server.queue(
        200,
        {
            "data": {
                "result": [
                    {
                        "ip-addresses": [
                            {
                                "ip-address": "192.0.2.10",
                                "ip-address-type": "ipv4",
                            }
                        ]
                    }
                ]
            }
        },
    )
    provider, clock = provider_with_clock(fake_server, profile)

    with pytest.raises(ProviderTimeoutError, match="VM 102"):
        provider.wait_for_ipv4(102, "pve02", timeout=1)

    assert clock.value == 1
    assert len(fake_server.requests.all()) == 1


def test_wait_for_ipv4_rejects_late_network_address(
    fake_server: FakeProxmoxServer, profile: ProxmoxProfile
) -> None:
    fake_server.queue(200, {"data": {}})
    fake_server.queue(200, {"data": {"result": []}})
    fake_server.queue(
        200,
        {
            "data": {
                "result": [
                    {
                        "ip-addresses": [
                            {
                                "ip-address": "192.0.2.10",
                                "ip-address-type": "ipv4",
                            }
                        ]
                    }
                ]
            }
        },
    )
    provider, clock = provider_with_clock(fake_server, profile)

    with pytest.raises(ProviderTimeoutError, match="VM 102"):
        provider.wait_for_ipv4(102, "pve02", timeout=1)

    assert clock.value == 1
    assert [request.method for request in fake_server.requests.all()] == ["POST", "GET"]


def test_health_check_uses_read_only_requests_and_reports_each_prerequisite(
    fake_server: FakeProxmoxServer, provider: ProxmoxProvider
) -> None:
    fake_server.queue(200, {"data": {"version": "8.3"}})
    fake_server.queue(200, {"data": [{"node": "pve02", "status": "online"}]})
    fake_server.queue(
        200,
        {
            "data": [
                {
                    "vmid": 9001,
                    "node": "pve02",
                    "name": "nixos-26.05-base-v2",
                    "template": 1,
                }
            ]
        },
    )
    fake_server.queue(
        200,
        {
            "data": {
                "name": "nixos-26.05-base-v2",
                "template": 1,
                "scsi0": "local-lvm:base-9001-disk-0",
                "net0": "virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0",
            }
        },
    )

    health = provider.health_check()

    assert {check.name for check in health.checks} == {
        "API",
        "Authentication",
        "Node",
        "Template identity",
        "Storage",
        "Network",
    }
    assert all(check.ok for check in health.checks)
    assert any("SDN.Use" in warning for warning in health.warnings)
    assert all(
        request.method not in {"POST", "PUT", "DELETE"}
        for request in fake_server.requests.all()
    )


def test_health_check_reports_every_prerequisite_when_api_is_unavailable(
    fake_server: FakeProxmoxServer, provider: ProxmoxProvider
) -> None:
    fake_server.queue(503, {"errors": "maintenance"})

    health = provider.health_check()

    assert [check.name for check in health.checks] == [
        "API",
        "Authentication",
        "Node",
        "Template identity",
        "Storage",
        "Network",
    ]
    assert not any(check.ok for check in health.checks)


def test_health_check_requires_an_exact_network_bridge_value(
    fake_server: FakeProxmoxServer, provider: ProxmoxProvider
) -> None:
    fake_server.queue(200, {"data": {"version": "8.3"}})
    fake_server.queue(200, {"data": [{"node": "pve02", "status": "online"}]})
    fake_server.queue(
        200,
        {
            "data": [
                {
                    "vmid": 9001,
                    "node": "pve02",
                    "name": "nixos-26.05-base-v2",
                    "template": 1,
                }
            ]
        },
    )
    fake_server.queue(
        200,
        {
            "data": {
                "scsi0": "local-lvm:base-9001-disk-0",
                "net0": "virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr01",
            }
        },
    )

    health = provider.health_check()

    network = next(check for check in health.checks if check.name == "Network")
    assert network.ok is False


def test_authentication_error_redacts_token_secret(
    fake_server: FakeProxmoxServer, provider: ProxmoxProvider
) -> None:
    fake_server.queue(401, {"errors": "private-value is not valid"})

    with pytest.raises(ProviderAuthenticationError) as caught:
        provider.allocate_vmid()

    assert "private-value" not in str(caught.value)


def test_transport_error_does_not_retain_request_headers(
    profile: ProxmoxProfile,
) -> None:
    authorization = "PVEAPIToken=learnlab@pam!automation=private-value"
    request = httpx.Request(
        "GET",
        "https://proxmox.example.test",
        headers={"Authorization": authorization},
    )

    class FailingClient:
        def request(self, *args: object, **kwargs: object) -> httpx.Response:
            raise httpx.RequestError("connection dropped", request=request)

    provider = ProxmoxProvider(
        profile,
        "private-value",
        client=cast(httpx.Client, FailingClient()),
    )

    with pytest.raises(ProviderOperationError) as caught:
        provider.allocate_vmid()

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "private-value" not in repr(caught.value)
    assert authorization not in repr(caught.value)


def test_error_body_is_redacted_before_being_bounded(
    fake_server: FakeProxmoxServer, profile: ProxmoxProfile
) -> None:
    fake_server.queue(500, {"errors": "x" * 2000})
    provider = ProxmoxProvider(
        profile,
        "x",
        client=httpx.Client(base_url=f"{fake_server.url}/api2/json", timeout=10.0),
    )

    with pytest.raises(ProviderOperationError) as caught:
        provider.allocate_vmid()

    detail = str(caught.value).split("HTTP 500: ", maxsplit=1)[1]
    assert len(detail) == 2000
    assert "x" not in detail
