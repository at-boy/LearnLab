from __future__ import annotations

import ipaddress
import time
from collections.abc import Callable, Mapping
from typing import cast
from urllib.parse import quote

import httpx

from learnlab.config import ProxmoxProfile
from learnlab.errors import (
    ProviderAuthenticationError,
    ProviderAuthorizationError,
    ProviderError,
    ProviderOperationError,
    ProviderTaskFailed,
    ProviderTimeoutError,
    redact,
)
from learnlab.providers.base import ProviderCheck, ProviderHealth, VmLocation


class ProxmoxProvider:
    """Synchronous adapter for the explicit Proxmox HTTP contract."""

    def __init__(
        self,
        profile: ProxmoxProfile,
        token_secret: str,
        *,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._profile = profile
        self._token_secret = token_secret
        self._client = client or httpx.Client(
            base_url=f"{profile.api_url.rstrip('/')}/api2/json",
            verify=profile.tls_verify,
            timeout=10.0,
        )
        self._clock = clock
        self._sleep = sleep

    def health_check(self) -> ProviderHealth:
        checks: list[ProviderCheck] = []
        provider_error = False
        try:
            version = self._request("GET", "/version")
            version_detail = self._string_value(version, "version") or "reachable"
            checks.append(ProviderCheck("API", True, version_detail))
        except ProviderError as error:
            checks.append(ProviderCheck("API", False, str(error)))
            checks.extend(self._unavailable_checks())
            return ProviderHealth(
                tuple(checks),
                (self._mutation_permissions_warning(),),
                provider_error=True,
            )

        nodes: object | None = None
        try:
            nodes = self._request("GET", "/nodes")
            checks.append(ProviderCheck("Authentication", True, "token accepted"))
        except ProviderError as error:
            checks.append(ProviderCheck("Authentication", False, str(error)))
            provider_error = True

        node_present = any(
            isinstance(item, Mapping) and item.get("node") == self._profile.node
            for item in self._as_list(nodes)
        )
        checks.append(
            ProviderCheck(
                "Node",
                node_present,
                self._profile.node
                if node_present
                else f"node {self._profile.node} not found",
            )
        )

        resources: object | None = None
        try:
            resources = self._request("GET", "/cluster/resources?type=vm")
        except ProviderError as error:
            checks.extend(
                (
                    ProviderCheck("Template identity", False, str(error)),
                    ProviderCheck(
                        "Storage", False, "template configuration unavailable"
                    ),
                    ProviderCheck(
                        "Network", False, "template configuration unavailable"
                    ),
                )
            )
            return ProviderHealth(
                tuple(checks),
                (self._mutation_permissions_warning(),),
                provider_error=True,
            )

        template = next(
            (
                item
                for item in self._as_list(resources)
                if isinstance(item, Mapping)
                and item.get("vmid") == self._profile.template_vmid
            ),
            None,
        )
        template_matches = isinstance(template, Mapping) and self._template_matches(
            template
        )
        checks.append(
            ProviderCheck(
                "Template identity",
                template_matches,
                "configured template matches profile"
                if template_matches
                else "configured template does not match profile",
            )
        )

        config: object | None = None
        try:
            config = self._request(
                "GET",
                f"/nodes/{self._profile.node}/qemu/{self._profile.template_vmid}/config",
            )
        except ProviderError as error:
            checks.extend(
                (
                    ProviderCheck("Storage", False, str(error)),
                    ProviderCheck("Network", False, str(error)),
                )
            )
            return ProviderHealth(
                tuple(checks),
                (self._mutation_permissions_warning(),),
                provider_error=True,
            )

        config_mapping = config if isinstance(config, Mapping) else {}
        storage_matches = self._has_storage(config_mapping)
        network_matches = self._has_network(config_mapping)
        checks.extend(
            (
                ProviderCheck(
                    "Storage",
                    storage_matches,
                    self._profile.storage
                    if storage_matches
                    else f"storage {self._profile.storage} not found",
                ),
                ProviderCheck(
                    "Network",
                    network_matches,
                    self._profile.network
                    if network_matches
                    else f"network {self._profile.network} not found",
                ),
            )
        )
        return ProviderHealth(
            tuple(checks),
            (self._mutation_permissions_warning(),),
            provider_error=provider_error,
        )

    def allocate_vmid(self) -> int:
        value = self._request("GET", "/cluster/nextid")
        try:
            return int(cast(str | int, value))
        except (TypeError, ValueError) as error:
            raise ProviderOperationError(
                "Proxmox allocate VMID returned an invalid value"
            ) from error

    def clone(self, vmid: int, name: str) -> str:
        return self._task_id(
            self._request(
                "POST",
                f"/nodes/{self._profile.node}/qemu/{self._profile.template_vmid}/clone",
                data={
                    "newid": str(vmid),
                    "name": name,
                    "full": "1",
                    "storage": self._profile.storage,
                },
            ),
            "clone",
        )

    def wait_for_task(self, node: str, upid: str, timeout: float) -> None:
        deadline = self._clock() + timeout
        path = f"/nodes/{node}/tasks/{quote(upid, safe='')}/status"
        while True:
            self._raise_if_deadline_reached(
                deadline, f"Timed out waiting for Proxmox task {upid}"
            )
            result = self._request("GET", path)
            self._raise_if_deadline_reached(
                deadline, f"Timed out waiting for Proxmox task {upid}"
            )
            if not isinstance(result, Mapping):
                raise ProviderOperationError(
                    "Proxmox task status returned an invalid value"
                )
            if result.get("status") == "stopped":
                exitstatus = result.get("exitstatus")
                if exitstatus == "OK":
                    return
                raise ProviderTaskFailed(
                    f"Proxmox task {upid} stopped with exit status {exitstatus!s}"
                )
            self._sleep_until_deadline(
                deadline, f"Timed out waiting for Proxmox task {upid}"
            )

    def locate_vm(self, vmid: int) -> VmLocation | None:
        resources = self._request("GET", "/cluster/resources?type=vm")
        for resource in self._as_list(resources):
            if not isinstance(resource, Mapping) or resource.get("vmid") != vmid:
                continue
            node = resource.get("node")
            status = resource.get("status")
            if isinstance(node, str) and isinstance(status, str):
                return VmLocation(node=node, status=status)
        return None

    def start(self, vmid: int, node: str) -> str:
        return self._task_id(
            self._request("POST", f"/nodes/{node}/qemu/{vmid}/status/start"), "start"
        )

    def stop(self, vmid: int, node: str) -> str:
        return self._task_id(
            self._request("POST", f"/nodes/{node}/qemu/{vmid}/status/stop"), "stop"
        )

    def wait_for_ipv4(self, vmid: int, node: str, timeout: float) -> str:
        deadline = self._clock() + timeout
        ping_path = f"/nodes/{node}/qemu/{vmid}/agent/ping"
        interfaces_path = f"/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces"
        timeout_message = f"Timed out waiting for guest IPv4 for VM {vmid}"
        while True:
            self._raise_if_deadline_reached(deadline, timeout_message)
            try:
                self._request("POST", ping_path)
                self._raise_if_deadline_reached(deadline, timeout_message)
                break
            except ProviderOperationError:
                self._sleep_until_deadline(deadline, timeout_message)
        while True:
            self._raise_if_deadline_reached(deadline, timeout_message)
            try:
                interfaces = self._request("GET", interfaces_path)
                self._raise_if_deadline_reached(deadline, timeout_message)
            except ProviderOperationError:
                self._sleep_until_deadline(deadline, timeout_message)
                continue
            address = self._first_ipv4(interfaces)
            if address is not None:
                return address
            self._sleep_until_deadline(deadline, timeout_message)

    def delete(self, vmid: int, node: str) -> str:
        return self._task_id(
            self._request("DELETE", f"/nodes/{node}/qemu/{vmid}"), "delete"
        )

    def _request(
        self, method: str, path: str, data: Mapping[str, str] | None = None
    ) -> object:
        headers = {
            "Authorization": (
                f"PVEAPIToken={self._profile.token_id}={self._token_secret}"
            )
        }
        transport_error: str | None = None
        response: httpx.Response | None = None
        try:
            response = self._client.request(method, path, data=data, headers=headers)
        except httpx.HTTPError as error:
            transport_error = self._safe_error(
                f"Proxmox {method} {path} request failed: {error}"
            )[:2000]
        if transport_error is not None:
            raise ProviderOperationError(transport_error)
        if response is None:
            raise ProviderOperationError(f"Proxmox {method} {path} did not respond")
        if not response.is_success:
            safe_detail = self._safe_error(response.text)[:2000]
            message = f"Proxmox {method} {path} failed with HTTP {response.status_code}"
            if safe_detail:
                message = f"{message}: {safe_detail}"
            if response.status_code == 401:
                raise ProviderAuthenticationError(message)
            if response.status_code == 403:
                raise ProviderAuthorizationError(message)
            raise ProviderOperationError(message)
        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderOperationError(
                f"Proxmox {method} {path} returned invalid JSON"
            ) from error
        if not isinstance(payload, Mapping) or "data" not in payload:
            raise ProviderOperationError(
                f"Proxmox {method} {path} returned an invalid response envelope"
            )
        return payload["data"]

    def _sleep_until_deadline(self, deadline: float, timeout_message: str) -> None:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise ProviderTimeoutError(timeout_message)
        self._sleep(min(2.0, remaining))

    def _raise_if_deadline_reached(self, deadline: float, timeout_message: str) -> None:
        if self._clock() >= deadline:
            raise ProviderTimeoutError(timeout_message)

    def _safe_error(self, text: str) -> str:
        return redact(text, {self._token_secret})

    @staticmethod
    def _as_list(value: object | None) -> list[object]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _string_value(value: object, key: str) -> str | None:
        if isinstance(value, Mapping) and isinstance(value.get(key), str):
            return cast(str, value[key])
        return None

    def _template_matches(self, template: Mapping[object, object]) -> bool:
        return (
            template.get("name") == self._profile.template_name
            and template.get("node") == self._profile.node
            and template.get("template") in {1}
        )

    def _has_storage(self, config: Mapping[object, object]) -> bool:
        return any(
            isinstance(value, str) and value.startswith(f"{self._profile.storage}:")
            for value in config.values()
        )

    def _has_network(self, config: Mapping[object, object]) -> bool:
        for value in config.values():
            if not isinstance(value, str):
                continue
            for option in value.split(","):
                key, separator, option_value = option.partition("=")
                if (
                    separator
                    and key == "bridge"
                    and option_value == self._profile.network
                ):
                    return True
        return False

    @staticmethod
    def _task_id(value: object, operation: str) -> str:
        if isinstance(value, str) and value:
            return value
        raise ProviderOperationError(f"Proxmox {operation} did not return a task ID")

    @staticmethod
    def _first_ipv4(interfaces: object) -> str | None:
        if not isinstance(interfaces, Mapping):
            return None
        result = interfaces.get("result")
        if not isinstance(result, list):
            return None
        for interface in result:
            if not isinstance(interface, Mapping):
                continue
            addresses = interface.get("ip-addresses")
            if not isinstance(addresses, list):
                continue
            for address in addresses:
                if not isinstance(address, Mapping):
                    continue
                if address.get("ip-address-type") != "ipv4":
                    continue
                candidate = address.get("ip-address")
                if not isinstance(candidate, str):
                    continue
                try:
                    parsed = ipaddress.ip_address(candidate)
                except ValueError:
                    continue
                if parsed.version == 4 and not parsed.is_loopback:
                    return candidate
        return None

    def _mutation_permissions_warning(self) -> str:
        return (
            "Read-only checks cannot prove scoped mutation permissions, including "
            f"SDN.Use for network {self._profile.network}."
        )

    @staticmethod
    def _unavailable_checks() -> tuple[ProviderCheck, ...]:
        detail = "not checked because the Proxmox API is unavailable"
        return (
            ProviderCheck("Authentication", False, detail),
            ProviderCheck("Node", False, detail),
            ProviderCheck("Template identity", False, detail),
            ProviderCheck("Storage", False, detail),
            ProviderCheck("Network", False, detail),
        )
