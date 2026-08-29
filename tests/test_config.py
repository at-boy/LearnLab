from __future__ import annotations

from collections.abc import Callable

import pytest

from learnlab.config import ProxmoxProfile, load_settings, resolve_token_secret
from learnlab.errors import ConfigurationError, redact

CONFIG = """
default_provider = "home-proxmox"

[providers.home-proxmox]
type = "proxmox"
api_url = "https://proxmox.example.test:8006/api2/json"
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


def test_loads_named_proxmox_profile(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")

    settings = load_settings(config)
    profile = settings.provider("home-proxmox")

    assert settings.default_provider == "home-proxmox"
    assert profile.template_vmid == 9001
    assert profile.tls_verify is True
    assert profile.ssh_identity_file.name == "learning-platform"


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


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ('api_url = "http://proxmox.example.test"', "https://"),
        ("template_vmid = 0", "positive"),
    ],
)
def test_rejects_invalid_profile_values(tmp_path, replacement, message):
    config = tmp_path / "config.toml"
    source = CONFIG
    if replacement.startswith("api_url"):
        source = source.replace(
            'api_url = "https://proxmox.example.test:8006/api2/json"', replacement
        )
    else:
        source = source.replace("template_vmid = 9001", replacement)
    config.write_text(source, encoding="utf-8")

    with pytest.raises(ConfigurationError, match=message):
        load_settings(config)
