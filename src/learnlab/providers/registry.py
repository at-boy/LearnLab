from __future__ import annotations

import httpx

from learnlab.config import Settings, resolve_token_secret
from learnlab.providers.base import Provider
from learnlab.providers.proxmox import ProxmoxProvider


def build_provider(
    settings: Settings, profile_name: str, client: httpx.Client | None = None
) -> Provider:
    """Build the configured provider for one named profile."""
    profile = settings.provider(profile_name)
    return ProxmoxProvider(
        profile,
        resolve_token_secret(profile),
        client=client,
    )
