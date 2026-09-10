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


def test_debian_binary_check_uses_privileged_bounded_lookup():
    path = ROOT / "nginx/courses/nginx-basics/lessons/00-installation/lesson.yaml"
    checks = yaml.safe_load(path.read_text())["steps"][0]["verifications"]
    check = next(item for item in checks if item["id"] == "nginx-binary-present")
    assert check["command"] == "sudo -n timeout 10 /usr/sbin/nginx -v"


def test_nixos_recovery_is_isolated_and_does_not_replay_relative_rollback():
    path = (
        ROOT
        / "nginx-nixos/courses/nginx-basics/lessons"
        / "05-logging-and-troubleshooting/lesson.yaml"
    )
    lesson = yaml.safe_load(path.read_text())
    step = lesson["steps"][1]
    assert "--rollback" not in step["instructions"]
    assert "isolated" in step["instructions"]
    assert "rollback" not in step["title"].lower()
    assert any(v["id"] == "isolated-config-rejected" for v in step["verifications"])


@pytest.mark.parametrize(
    "family,check_id,answer,wrong",
    [
        (
            "nginx-nixos",
            "explain-dry-build",
            "nixos-rebuild build",
            "not nixos-rebuild build",
        ),
        ("nginx-nixos", "explain-restart-durability", "no", "yes"),
        (
            "nginx-nixos",
            "explain-list-generations",
            "--list-generations",
            "--delete-generations",
        ),
        ("nginx", "explain-x-forwarded-for", "proxy address", "client address"),
        ("nginx-nixos", "explain-forwarded-headers", "proxy address", "client address"),
        ("nginx", "explain-package-source", "apt install nginx", "adapt"),
        ("nginx", "explain-reload-vs-restart", "reload", "drop connections"),
        (
            "nginx",
            "explain-active-config",
            "/etc/nginx/sites-enabled",
            "not sites-enabled",
        ),
        ("nginx", "explain-config-test", "syntax; no", "invalid"),
        ("nginx", "explain-symlink-choice", "single source", "out of sync"),
        (
            "nginx-nixos",
            "explain-the-apply-command",
            "nixos-rebuild switch",
            "not nixos-rebuild switch",
        ),
        (
            "nginx-nixos",
            "explain-source-of-truth",
            "configuration.nix",
            "not in any module",
        ),
        (
            "nginx-nixos",
            "explain-virtual-hosts-option",
            "services.nginx.virtualHosts",
            "not virtualHosts",
        ),
    ],
)
def test_nginx_knowledge_answers_are_whole_responses(family, check_id, answer, wrong):
    import re

    checks = [
        check
        for path in (ROOT / family).rglob("lesson.yaml")
        for step in yaml.safe_load(path.read_text())["steps"]
        for check in step.get("verifications", [])
        if check["id"] == check_id
    ]
    assert len(checks) == 1
    pattern = checks[0]["matches"]
    assert re.search(pattern, answer)
    for rejected in (wrong, "not " + answer, "unrelated " + answer + " unrelated"):
        assert not re.search(pattern, rejected), rejected
