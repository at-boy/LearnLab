from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

from platformdirs import PlatformDirs

from learnlab.errors import ConfigurationError

_PROFILE_KEYS = {
    "type",
    "api_url",
    "token_id",
    "token_secret_env",
    "template_vmid",
    "template_name",
    "node",
    "storage",
    "network",
    "ssh_user",
    "ssh_identity_file",
    "tls_verify",
}
_PROFILE_OPTIONAL_KEYS = {"template_capabilities"}
_CAPABILITY_ID = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*\Z")
_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


@dataclass(frozen=True)
class ProxmoxProfile:
    name: str
    api_url: str
    token_id: str
    token_secret_env: str
    template_vmid: int
    template_name: str
    node: str
    storage: str
    network: str
    ssh_user: str
    ssh_identity_file: Path
    tls_verify: bool
    template_capabilities: tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        """Return the immutable non-secret identity of this provider target."""
        return provider_fingerprint(self)


@dataclass(frozen=True)
class Settings:
    default_provider: str
    providers: Mapping[str, ProxmoxProfile]

    def provider(self, name: str) -> ProxmoxProfile:
        try:
            return self.providers[name]
        except KeyError as error:
            raise ConfigurationError(f"Unknown provider profile: {name}") from error


@dataclass(frozen=True)
class RequestedProfiles:
    """Valid requested profiles and isolated errors for invalid requested names."""

    settings: Settings
    errors: Mapping[str, ConfigurationError]


def config_path() -> Path:
    """Return the default XDG configuration file path."""
    return PlatformDirs("learnlab").user_config_path / "config.toml"


def state_dir() -> Path:
    """Return the default XDG state directory."""
    return PlatformDirs("learnlab").user_state_path


def load_settings(path: Path | None = None) -> Settings:
    """Load named provider profiles from a TOML file."""
    data = _load_config_data(path)

    default_provider = data.get("default_provider")
    providers = data.get("providers")
    if not isinstance(default_provider, str) or not isinstance(providers, dict):
        raise ConfigurationError(
            "Configuration requires default_provider and providers"
        )

    parsed_profiles: dict[str, ProxmoxProfile] = {}
    for name, profile_data in providers.items():
        if not isinstance(name, str) or not isinstance(profile_data, dict):
            raise ConfigurationError("Provider profiles must be named tables")
        parsed_profiles[name] = _parse_proxmox_profile(name, profile_data)
    return Settings(
        default_provider=default_provider,
        providers=MappingProxyType(parsed_profiles),
    )


def load_requested_profiles(
    names: Iterable[str], path: Path | None = None
) -> RequestedProfiles:
    """Load requested profiles while isolating validation errors by name."""
    requested_names = tuple(dict.fromkeys(names))
    try:
        data = _load_config_data(path)
    except ConfigurationError as load_error:
        return _requested_profile_result(
            {}, {name: load_error for name in requested_names}
        )

    providers = data.get("providers")
    if not isinstance(providers, dict):
        providers_error = ConfigurationError("Configuration requires providers")
        return _requested_profile_result(
            {}, {name: providers_error for name in requested_names}
        )

    parsed_profiles: dict[str, ProxmoxProfile] = {}
    errors: dict[str, ConfigurationError] = {}
    for name in requested_names:
        profile_data = providers.get(name)
        if profile_data is None:
            errors[name] = ConfigurationError(f"Unknown provider profile: {name}")
            continue
        if not isinstance(profile_data, dict):
            errors[name] = ConfigurationError(
                f"Provider profile {name} must be a named table"
            )
            continue
        try:
            parsed_profiles[name] = _parse_proxmox_profile(name, profile_data)
        except ConfigurationError as error:
            errors[name] = error

    default_provider = data.get("default_provider")
    return _requested_profile_result(
        parsed_profiles,
        errors,
        default_provider if isinstance(default_provider, str) else "",
    )


def resolve_token_secret(profile: ProxmoxProfile) -> str:
    """Resolve a profile's token secret only from its declared environment variable."""
    secret = os.environ.get(profile.token_secret_env)
    if not secret:
        raise ConfigurationError(
            "Missing required token secret environment variable: "
            f"{profile.token_secret_env}"
        )
    return secret


def provider_fingerprint(profile: ProxmoxProfile) -> str:
    """Hash the canonical non-secret fields that own a disposable VM."""
    identity = {
        "api_origin": profile.api_url,
        "node": profile.node,
        "template_name": profile.template_name,
        "template_vmid": profile.template_vmid,
        "token_id": profile.token_id,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def _load_config_data(path: Path | None) -> dict[str, Any]:
    config_file = path if path is not None else config_path()
    try:
        with config_file.open("rb") as file:
            return tomllib.load(file)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(
            f"Unable to load configuration: {config_file}"
        ) from error


def _requested_profile_result(
    profiles: dict[str, ProxmoxProfile],
    errors: dict[str, ConfigurationError],
    default_provider: str = "",
) -> RequestedProfiles:
    return RequestedProfiles(
        settings=Settings(
            default_provider=default_provider,
            providers=MappingProxyType(profiles),
        ),
        errors=MappingProxyType(errors),
    )


def _parse_proxmox_profile(name: str, data: dict[str, Any]) -> ProxmoxProfile:
    allowed_keys = _PROFILE_KEYS | _PROFILE_OPTIONAL_KEYS
    if not _PROFILE_KEYS.issubset(data) or not set(data).issubset(allowed_keys):
        missing = sorted(_PROFILE_KEYS - set(data))
        unknown = sorted(set(data) - allowed_keys)
        details = []
        if missing:
            details.append(f"missing keys: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown keys: {', '.join(unknown)}")
        raise ConfigurationError(
            f"Invalid provider profile {name}: {'; '.join(details)}"
        )
    if data["type"] != "proxmox":
        raise ConfigurationError(
            f"Unsupported provider type for {name}: {data['type']}"
        )

    api_url = _normalize_api_origin(_required_string(data, "api_url", name), name)
    template_vmid = data["template_vmid"]
    if (
        not isinstance(template_vmid, int)
        or isinstance(template_vmid, bool)
        or template_vmid <= 0
    ):
        raise ConfigurationError(
            f"Provider profile {name} template_vmid must be positive"
        )
    tls_verify = data["tls_verify"]
    if not isinstance(tls_verify, bool):
        raise ConfigurationError(
            f"Provider profile {name} tls_verify must be a boolean"
        )
    template_capabilities = _capability_list(
        data.get("template_capabilities", []), "template_capabilities", name
    )

    return ProxmoxProfile(
        name=name,
        api_url=api_url,
        token_id=_required_string(data, "token_id", name),
        token_secret_env=_required_string(data, "token_secret_env", name),
        template_vmid=template_vmid,
        template_name=_required_string(data, "template_name", name),
        node=_required_string(data, "node", name),
        storage=_required_string(data, "storage", name),
        network=_required_string(data, "network", name),
        ssh_user=_required_string(data, "ssh_user", name),
        ssh_identity_file=Path(
            _required_string(data, "ssh_identity_file", name)
        ).expanduser(),
        tls_verify=tls_verify,
        template_capabilities=template_capabilities,
    )


def _capability_list(value: object, key: str, profile_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigurationError(
            f"Provider profile {profile_name} {key} must be an explicit list"
        )
    capabilities = tuple(value)
    if not all(
        isinstance(capability, str) and _CAPABILITY_ID.fullmatch(capability)
        for capability in capabilities
    ):
        raise ConfigurationError(
            f"Provider profile {profile_name} {key} entries must be capability IDs"
        )
    if len(set(capabilities)) != len(capabilities):
        raise ConfigurationError(
            f"Provider profile {profile_name} has duplicate {key} IDs"
        )
    return capabilities


def _required_string(data: dict[str, Any], key: str, profile_name: str) -> str:
    value = data[key]
    if not isinstance(value, str) or not value:
        raise ConfigurationError(
            f"Provider profile {profile_name} {key} must be a nonempty string"
        )
    return value


def _normalize_api_origin(value: str, profile_name: str) -> str:
    message = (
        f"Provider profile {profile_name} api_url must be an HTTPS origin "
        "without credentials, path, query, or fragment"
    )
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ConfigurationError(message) from error
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or "?" in value
        or "#" in value
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ConfigurationError(message)
    host = parsed.hostname.lower()
    if not _valid_hostname(host) or port == 0:
        raise ConfigurationError(message)
    rendered_host = f"[{host}]" if ":" in host else host
    rendered_port = f":{port}" if port is not None and port != 443 else ""
    return f"https://{rendered_host}{rendered_port}"


def _valid_hostname(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        labels = host.split(".")
        return len(host) <= 253 and all(
            _HOST_LABEL.fullmatch(label) for label in labels
        )
    return True
