from __future__ import annotations

import pytest
from typer.testing import CliRunner

from learnlab.providers.base import ProviderCheck, ProviderHealth

CONFIG = '''
default_provider = "home-proxmox"

[providers.home-proxmox]
type = "proxmox"
api_url = "https://proxmox.example.test:8006/api2/json"
token_id = "learnlab@pam!automation"
token_secret_env = "LEARNLAB_HOME_SECRET"
template_vmid = 9001
template_name = "debian-12-learning"
node = "pve"
storage = "local-lvm"
network = "vmbr0"
ssh_user = "student"
ssh_identity_file = "~/.ssh/learning-platform"
tls_verify = true
'''


class FakeHealthProvider:
    def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            checks=(ProviderCheck("Template identity", True, "matches"),),
            warnings=("Grant SDN.Use for network vmbr0.",),
        )


@pytest.fixture
def tmp_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path):
    config_dir = tmp_path / "config" / "learnlab"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path


@pytest.fixture
def fake_health_provider() -> FakeHealthProvider:
    return FakeHealthProvider()


def test_provider_test_uses_named_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_xdg,
    fake_health_provider: FakeHealthProvider,
) -> None:
    from learnlab.cli import app

    def provider_factory(
        settings, profile_name: str, client=None
    ) -> FakeHealthProvider:
        assert settings.provider(profile_name).name == "home-proxmox"
        assert client is None
        return fake_health_provider

    monkeypatch.setenv("LEARNLAB_HOME_SECRET", "secret")
    monkeypatch.setattr("learnlab.cli.provider_factory", provider_factory)
    result = CliRunner().invoke(app, ["provider", "test", "home-proxmox"])

    assert result.exit_code == 0
    assert "home-proxmox" in result.stdout
    assert "Template identity" in result.stdout
    assert "SDN.Use" in result.stdout
    assert "secret" not in result.stdout


def test_provider_test_unknown_profile_is_actionable(tmp_xdg) -> None:
    from learnlab.cli import app

    result = CliRunner().invoke(app, ["provider", "test", "missing"])

    assert result.exit_code == 2
    assert "Unknown provider profile: missing" in result.stdout
