from __future__ import annotations

from collections.abc import Callable

import pytest

from learnlab.config import ProxmoxProfile


@pytest.fixture
def profile_fixture() -> Callable[..., ProxmoxProfile]:
    def build_profile(**overrides: object) -> ProxmoxProfile:
        values: dict[str, object] = {
            "name": "home-proxmox",
            "api_url": "https://proxmox.example.test:8006/api2/json",
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
