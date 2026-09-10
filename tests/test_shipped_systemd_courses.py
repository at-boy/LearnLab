"""Offline curriculum contracts; no systemd guest is operated by these tests."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1] / "src/learnlab/collections"
FAMILIES = ["systemd-debian", "systemd-nixos"]


def lesson(family, number):
    base = ROOT / family / "courses/service-authoring/lessons"
    return yaml.safe_load(next(base.glob(f"{number:02}-*/lesson.yaml")).read_text())


def commands(data):
    return "\n".join(
        check.get("command", "")
        for step in data["steps"]
        for check in step["verifications"]
    )


@pytest.mark.parametrize(
    "family,os_cap", zip(FAMILIES, ["os.debian.13", "os.nixos"], strict=True)
)
def test_guest_contract(family, os_cap):
    path = ROOT / family / "courses/service-authoring/course.yaml"
    assert path.exists(), "Systemd family must ship in canonical curriculum"
    course = yaml.safe_load(path.read_text())
    assert {os_cap, "tool.systemd", "tool.coreutils", "tool.sudo"} <= set(
        course["environment"].get("guest_capabilities", [])
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_fresh_restart_chain_sandbox_and_timer_probes(family):
    restart = commands(lesson(family, 2))
    assert "--signal=KILL" in restart
    assert "NRestarts" in restart and "InvocationID" in restart
    assert "grep -c started" not in restart
    chain = commands(lesson(family, 3))
    assert "rm -f" in chain and "input.txt" in chain and "output.txt" in chain
    assert "Wants" in chain and "After" in chain
    sandbox = commands(lesson(family, 5))
    assert "rm -f" in sandbox and "Result" in sandbox
    assert "PrivateTmp" in sandbox and "grep -qx sandboxed" in sandbox
    timer = commands(lesson(family, 6))
    assert "LastTriggerUSec" in timer and "NextElapseUSecRealtime" in timer
    assert "rm -f" in timer and "sleep 1" in timer


@pytest.mark.parametrize("family", FAMILIES)
def test_capstone_actually_checks_failure_then_repair(family):
    command = commands(lesson(family, 7))
    assert "rm -f" in command and "if systemctl start" in command
    assert '"exit-code"' in command and '"success"' in command
    assert "InvocationID" in command and "journalctl" in command


@pytest.mark.parametrize("family", FAMILIES)
def test_wrong_restart_answer_rejected(family):
    data = lesson(family, 2)
    check = data["steps"][1]["verifications"][0]
    assert not re.search(check["matches"], "any signal including SIGTERM")
    assert re.search(check["matches"], "SIGKILL")


def test_nixos_generated_units_and_test_activation_are_accurate():
    assert "test -L /etc/systemd/system" not in commands(lesson("systemd-nixos", 0))
    text = str(lesson("systemd-nixos", 7))
    assert "does activate" in text and "--rollback switch" in text


@pytest.mark.parametrize("family", FAMILIES)
def test_systemd_catalog_schema_loads(family):
    from learnlab.curriculum import CurriculumCatalog

    course = CurriculumCatalog(ROOT).load_course(f"{family}/service-authoring")
    assert len(course.lessons) == 8


def test_debian_printf_escapes_systemd_percent_specifier():
    instructions = lesson("systemd-debian", 4)["steps"][1]["instructions"]
    assert 'printf "%%s\\n"' in instructions


def test_nixos_unit_inspection_is_bounded_and_without_pager():
    instructions = lesson("systemd-nixos", 1)["steps"][1]["instructions"]
    assert "timeout 10 systemctl --no-pager cat hello-oneshot.service" in instructions


def test_debian_account_lookup_only_creates_for_missing_account():
    instructions = lesson("systemd-debian", 4)["steps"][0]["instructions"]
    assert "timeout 10 getent passwd appuser" in instructions
    assert "lookup_status=$?" in instructions
    assert 'test "$lookup_status" -eq 2' in instructions
    assert 'exit "$lookup_status"' in instructions


def test_nixos_account_remediation_does_not_require_debian_env_file():
    check = lesson("systemd-nixos", 4)["steps"][0]["verifications"][0]
    assert "Debian" not in check["failure_message"]
    assert "env file" not in check["failure_message"]
