from __future__ import annotations

from collections.abc import Callable

import pytest

import learnlab.config as config_module
from learnlab.config import ProxmoxProfile, load_settings, resolve_token_secret
from learnlab.errors import ConfigurationError, redact

CONFIG = """
default_provider = "home-proxmox"

[providers.home-proxmox]
type = "proxmox"
api_url = "https://PROXMOX.example.test:8006/"
token_id = "learnlab@pam!automation"
token_secret_env = "LEARNLAB_TEST_SECRET"
template_vmid = 9001
template_name = "debian-12-learning"
node = "pve"
storage = "local-lvm"
network = "vmbr0"
ssh_user = "student"
ssh_identity_file = "~/.ssh/learning-platform"
tls_verify = true
"""

CAPABILITIES = 'template_capabilities = ["os.debian.13", "tool.curl"]\n'


def test_loads_named_proxmox_profile(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")

    settings = load_settings(config)
    profile = settings.provider("home-proxmox")

    assert settings.default_provider == "home-proxmox"
    assert profile.template_vmid == 9001
    assert profile.api_url == "https://proxmox.example.test:8006"
    assert profile.tls_verify is True
    assert profile.ssh_identity_file.name == "learning-platform"
    assert profile.template_capabilities == ()


def test_profile_loads_template_capabilities(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG + CAPABILITIES, encoding="utf-8")

    profile = load_settings(config).provider("home-proxmox")

    assert profile.template_capabilities == ("os.debian.13", "tool.curl")


@pytest.mark.parametrize(
    "capabilities",
    [
        '"os.nixos"',
        '["OS.nixos"]',
        '["os/debian/13"]',
        '["os.nixos", "os.nixos"]',
    ],
)
def test_profile_rejects_invalid_template_capabilities(
    tmp_path, capabilities: str
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        CONFIG + f"template_capabilities = {capabilities}\n", encoding="utf-8"
    )

    with pytest.raises(ConfigurationError, match="template_capabilities"):
        load_settings(config)


def test_secret_is_resolved_only_from_named_environment(
    monkeypatch, profile_fixture: Callable[..., ProxmoxProfile]
):
    env_name = "LEARNLAB_TEST_SECRET"
    profile = profile_fixture(**{"token_secret_env": env_name})
    monkeypatch.setenv("LEARNLAB_TEST_SECRET", "private-value")

    assert resolve_token_secret(profile) == "private-value"
    assert "private-value" not in repr(profile)


def test_missing_secret_names_variable_without_disclosing_values(
    monkeypatch, profile_fixture: Callable[..., ProxmoxProfile]
):
    env_name = "LEARNLAB_TEST_SECRET"
    profile = profile_fixture(**{"token_secret_env": env_name})
    monkeypatch.delenv("LEARNLAB_TEST_SECRET", raising=False)

    with pytest.raises(ConfigurationError, match="LEARNLAB_TEST_SECRET"):
        resolve_token_secret(profile)


def test_redact_replaces_each_nonempty_secret():
    text = "Authorization: PVEAPIToken=id=private-value"

    assert (
        redact(text, {"", "private-value"})
        == "Authorization: PVEAPIToken=id=[REDACTED]"
    )


def test_unknown_profile_is_rejected(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Unknown provider profile: missing"):
        load_settings(config).provider("missing")


def test_invalid_provider_type_is_rejected(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        CONFIG.replace('type = "proxmox"', 'type = "other"'), encoding="utf-8"
    )

    with pytest.raises(ConfigurationError, match="Unsupported provider type"):
        load_settings(config)


def test_requested_profile_loading_isolates_malformed_unrelated_table(tmp_path):
    config = tmp_path / "config.toml"
    malformed_and_valid = CONFIG.replace(
        "[providers.home-proxmox]",
        """[providers.malformed]
type = "proxmox"
api_url = "https://malformed.example.test"

[providers.home-proxmox]""",
    )
    config.write_text(malformed_and_valid, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="malformed"):
        load_settings(config)

    loaded = config_module.load_requested_profiles(
        ("malformed", "home-proxmox"), config
    )

    assert set(loaded.settings.providers) == {"home-proxmox"}
    assert loaded.settings.provider("home-proxmox").template_vmid == 9001
    assert set(loaded.errors) == {"malformed"}
    assert "missing keys" in str(loaded.errors["malformed"])


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ('api_url = "http://proxmox.example.test"', "HTTPS origin"),
        ("template_vmid = 0", "positive"),
    ],
)
def test_rejects_invalid_profile_values(tmp_path, replacement, message):
    config = tmp_path / "config.toml"
    source = CONFIG
    if replacement.startswith("api_url"):
        source = source.replace(
            'api_url = "https://PROXMOX.example.test:8006/"', replacement
        )
    else:
        source = source.replace("template_vmid = 9001", replacement)
    config.write_text(source, encoding="utf-8")

    with pytest.raises(ConfigurationError, match=message):
        load_settings(config)


@pytest.mark.parametrize(
    "api_url",
    [
        "https://user:password@proxmox.example.test:8006",
        "https://proxmox.example.test:8006?debug=true",
        "https://proxmox.example.test:8006?",
        "https://proxmox.example.test:8006#fragment",
        "https://proxmox.example.test:8006#",
        "https://proxmox.example.test:8006/api2/json",
        "https://proxmox.example.test:8006/other",
        "https://proxmox.example.test:not-a-port",
        "https:///missing-host",
        "https://bad_host.example.test",
    ],
)
def test_api_url_rejects_anything_other_than_an_https_origin(
    tmp_path, api_url: str
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        CONFIG.replace(
            'api_url = "https://PROXMOX.example.test:8006/"',
            f'api_url = "{api_url}"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="HTTPS origin"):
        load_settings(config)


def test_provider_fingerprint_is_stable_and_contains_no_secret(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv("LEARNLAB_TEST_SECRET", "private-value")

    first = load_settings(config).provider("home-proxmox")
    second = load_settings(config).provider("home-proxmox")

    assert first.fingerprint == second.fingerprint
    assert first.fingerprint.startswith("sha256:")
    assert "private-value" not in first.fingerprint
