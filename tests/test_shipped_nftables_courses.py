"""Regressions for packet paths and safe execution in the draft nftables family."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from learnlab.curriculum import CurriculumCatalog

ROOT = Path(__file__).parents[1] / "src/learnlab/collections"
FAMILIES = ("nftables-debian13", "nftables-nixos")


@pytest.fixture(params=FAMILIES)
def course_dir(request: pytest.FixtureRequest) -> Path:
    return ROOT / str(request.param) / "courses/nftables-basics"


def lessons(course_dir: Path) -> list[dict[str, Any]]:
    return [
        yaml.safe_load(p.read_text()) for p in course_dir.glob("lessons/*/lesson.yaml")
    ]


def test_nat_is_deferred_without_false_loopback_probe(course_dir: Path) -> None:
    course = yaml.safe_load((course_dir / "course.yaml").read_text())
    assert "port-forwarding-with-nat" not in course["lessons"]
    nat = next(x for x in lessons(course_dir) if x["id"] == "port-forwarding-with-nat")
    assert "multi-machine" in nat["steps"][0]["instructions"]
    assert "127.0.0.1:8081" not in str(nat)


def test_logging_has_objective_fresh_non_loopback_probe(course_dir: Path) -> None:
    lesson = next(
        x for x in lessons(course_dir) if x["id"] == "logging-and-troubleshooting"
    )
    step = lesson["steps"][0]
    assert "127.0.0.1:9999" not in str(step)
    commands = "\n".join(v.get("command", "") for v in step["verifications"])
    for required in (
        "netns",
        "veth",
        "--max-time",
        "trap",
        "--after-cursor",
        "DPT=9999",
    ):
        assert required in commands
    assert "intentionally locked yourself out" not in str(lesson)


def test_prerequisites_and_draft_capabilities(course_dir: Path) -> None:
    course = CurriculumCatalog(ROOT).load_course(
        f"{course_dir.parents[1].name}/nftables-basics"
    )
    assert course.maturity.value == "draft"
    caps = course.environment.guest_capabilities
    assert any(c.startswith("os.") for c in caps)
    assert {"tool.nft", "tool.ip", "tool.curl", "tool.python3"} <= set(caps)
    first = course.lessons[0].steps[0].instructions
    assert "cumulative" in first and "fresh" in first and "passwordless" in first


def test_text_answers_reject_negation_and_unrelated_words(course_dir: Path) -> None:
    patterns = {
        v["id"]: v["matches"]
        for lesson in lessons(course_dir)
        for s in lesson["steps"]
        for v in s["verifications"]
        if v["type"] == "text-evidence"
    }
    cases = {
        "explain-loopback-caveat": (
            "loopback is accepted before the port rule",
            "loopback is not accepted",
        ),
        "explain-post-nat-port": ("8080", "not 8080, use 8081"),
    }
    for key, (right, wrong) in cases.items():
        assert re.search(patterns[key], right)
        assert not re.search(patterns[key], wrong)


def test_no_nixos_usr_sbin_or_dry_build_claim(course_dir: Path) -> None:
    if "nixos" in str(course_dir):
        content = str(lessons(course_dir))
        assert "/usr/sbin/nft" not in content
        assert "dry-build" not in content


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("fresh", 0),
        ("stale", 1),
        ("refused", 1),
        ("overlap", 1),
        ("route-failure", 1),
        ("ns-collision", 1),
        ("link-collision", 1),
        ("configure-failure", 1),
    ],
)
def test_logging_shell_requires_fresh_drop_and_cleans_up(
    course_dir: Path, tmp_path: Path, scenario: str, expected: int
) -> None:
    """Exercise the actual probe shell offline with command fakes, never a guest."""
    import os
    import shlex
    import subprocess
    import sys

    lesson = next(
        x for x in lessons(course_dir) if x["id"] == "logging-and-troubleshooting"
    )
    command = lesson["steps"][0]["verifications"][0]["command"]
    script = shlex.split(command)[-1]
    fake = tmp_path / "fake"
    fake.write_text(
        f"#!{sys.executable}\n"
        + """import os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
state = pathlib.Path(os.environ['PROBE_STATE'])
with (state / 'calls').open('a') as log:
    log.write(name + ' ' + ' '.join(args) + '\\n')
scenario = os.environ['PROBE_SCENARIO']
if name == 'ip' and 'route' in args:
    if scenario == 'route-failure': sys.exit(1)
    if '-j' in args:
        print('[{"dst": "192.0.0.0/16"}]' if scenario == 'overlap' else
              '[{"dst": "default"}, {"dst": "10.0.0.0/24"}]')
    elif scenario == 'overlap': print('192.0.0.0/16 dev existing')
if name == 'ip' and args[:2] == ['netns', 'add'] and scenario == 'ns-collision':
    sys.exit(1)
if name == 'ip' and args[:2] == ['addr', 'add'] and scenario == 'configure-failure':
    sys.exit(1)
if name == 'ip' and args[:2] == ['link', 'add']:
    if scenario == 'link-collision': sys.exit(1)
    (state / 'interface').write_text(args[2])
if name == 'ip' and args[:2] == ['netns', 'exec']:
    sys.exit(7 if os.environ['PROBE_SCENARIO'] == 'refused' else 28)
if name == 'journalctl':
    if '--show-cursor' in args:
        print('-- cursor: previous-entry')
    elif os.environ['PROBE_SCENARIO'] == 'fresh':
        print('nft-drop: IN=' + (state / 'interface').read_text() +
              ' OUT= SRC=192.0.2.2 DST=192.0.2.1 DPT=9999 ')
"""
    )
    fake.chmod(0o755)
    for name in ("ip", "journalctl", "sleep"):
        (tmp_path / name).symlink_to(fake)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "PROBE_STATE": str(tmp_path),
        "PROBE_SCENARIO": scenario,
    }
    result = subprocess.run(  # noqa: S603 - repository-owned script with fake commands
        ["/bin/sh", "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == expected, result.stderr
    calls = (tmp_path / "calls").read_text()
    assert ("ip netns del ll-probe-" in calls) == (
        scenario not in {"overlap", "route-failure", "ns-collision"}
    )
    assert ("ip link del llh" in calls) == (
        scenario not in {"overlap", "route-failure", "ns-collision", "link-collision"}
    )
    if scenario in {"overlap", "route-failure"}:
        assert "ip netns add" not in calls


def test_nixos_service_build_precedes_timer(course_dir: Path) -> None:
    if "nixos" not in str(course_dir):
        return
    lesson = next(x for x in lessons(course_dir) if x["id"] == "allowing-a-service")
    instructions = lesson["steps"][1]["instructions"]
    assert "With your safety net armed" not in instructions
    assert instructions.index("nixos-rebuild build") < instructions.index(
        "arm and verify"
    )
    assert instructions.index("arm and verify") < instructions.index(
        "switch-to-configuration"
    )
