"""Offline regression contracts; these checks do not certify a live guest."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1] / "src/learnlab/collections"


@pytest.mark.parametrize(
    "family,os_cap", [("nginx", "os.debian.13"), ("nginx-nixos", "os.nixos")]
)
def test_nginx_guest_contract(family, os_cap):
    course = yaml.safe_load(
        (ROOT / family / "courses/nginx-basics/course.yaml").read_text()
    )
    assert {os_cap, "tool.curl"} <= set(
        course["environment"].get("guest_capabilities", [])
    )


def test_nixos_nginx_response_is_nested_under_virtual_host():
    path = (
        ROOT
        / "nginx-nixos/courses/nginx-basics/lessons/00-enabling-the-service/lesson.yaml"
    )
    text = yaml.safe_load(path.read_text())["steps"][1]["instructions"]
    assert 'services.nginx.virtualHosts."learnlab.local"' in text
    assert "services.nginx = {\n  enable = true;\n  locations" not in text


@pytest.mark.parametrize("family", ["nginx", "nginx-nixos"])
def test_remote_probes_are_bounded_and_not_source_greps(family):
    for path in (ROOT / family).rglob("lesson.yaml"):
        lesson = yaml.safe_load(path.read_text())
        for step in lesson["steps"]:
            for check in step.get("verifications", []):
                command = check.get("command", "")
                if "curl " in command:
                    assert "--max-time" in command, check["id"]
                    assert "--fail" in command, check["id"]
                assert "grep -q 'recommendedProxySettings'" not in command
                assert "grep -q 'virtualHosts'" not in command


@pytest.mark.parametrize("family", ["nginx", "nginx-nixos"])
def test_proxy_proves_forwarded_header_and_logs_use_fresh_request(family):
    lessons = ROOT / family / "courses/nginx-basics/lessons"
    proxy = (lessons / "04-reverse-proxy/lesson.yaml").read_text()
    logs = (lessons / "05-logging-and-troubleshooting/lesson.yaml").read_text()
    assert "$http_x_forwarded_for" in proxy
    assert "mktemp" in logs
    assert "tail -c" in logs
    assert "test -f /var/log/nginx/access.log" not in logs


def test_restart_explanation_rejects_unrelated_no_substring():
    import re

    path = (
        ROOT
        / "nginx-nixos/courses/nginx-basics/lessons/01-rebuild-workflow/lesson.yaml"
    )
    check = yaml.safe_load(path.read_text())["steps"][0]["verifications"][1]
    assert re.search(check["matches"], "no")
    assert not re.search(check["matches"], "I know it persists")
