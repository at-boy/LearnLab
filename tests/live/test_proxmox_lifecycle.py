"""Destructive, explicitly opted-in acceptance coverage for Proxmox."""

from __future__ import annotations

import ipaddress
import os

import pytest

from learnlab.config import load_settings
from learnlab.providers.registry import build_provider


@pytest.mark.live
def test_real_proxmox_lifecycle_requires_explicit_opt_in() -> None:
    """Clone, start, discover, stop, and delete a real disposable VM."""
    profile_name = os.environ.get("LEARNLAB_LIVE_PROFILE")
    if os.environ.get("LEARNLAB_RUN_LIVE_PROXMOX") != "1" or not profile_name:
        pytest.skip(
            "set LEARNLAB_RUN_LIVE_PROXMOX=1 and LEARNLAB_LIVE_PROFILE=<profile> "
            "to allow real VM mutation"
        )

    settings = load_settings()
    provider = build_provider(settings, profile_name)
    vmid = provider.allocate_vmid()
    node = settings.provider(profile_name).node
    try:
        clone_upid = provider.clone(vmid, f"learnlab-live-{vmid}")
        provider.wait_for_task(node, clone_upid, timeout=300)

        location = provider.locate_vm(vmid)
        assert location is not None
        start_upid = provider.start(vmid, location.node)
        provider.wait_for_task(location.node, start_upid, timeout=120)

        address = provider.wait_for_ipv4(vmid, location.node, timeout=180)
        assert ipaddress.ip_address(address).version == 4
    finally:
        location = provider.locate_vm(vmid)
        if location is not None:
            if location.status == "running":
                stop_upid = provider.stop(vmid, location.node)
                provider.wait_for_task(location.node, stop_upid, timeout=120)
            delete_upid = provider.delete(vmid, location.node)
            provider.wait_for_task(location.node, delete_upid, timeout=300)
        assert provider.locate_vm(vmid) is None
