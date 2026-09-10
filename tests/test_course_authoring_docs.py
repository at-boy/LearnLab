from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from learnlab.cli import app

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "LearnLab-Course-Authoring-Guide.md"
README = ROOT / "README.md"


def _start_commands(text: str) -> list[str]:
    return re.findall(r"learnlab start [^`\n]+", text)


def test_guide_documents_the_implemented_certification_contract() -> None:
    guide = GUIDE.read_text(encoding="utf-8")

    assert "src/learnlab/collections/" in guide
    assert "keep the two in sync" not in guide.lower()
    assert "learnlab validate" in guide
    assert all(
        maturity in guide
        for maturity in ("draft", "offline-validated", "live-validated")
    )
    assert "certifications.yaml" in guide
    assert "SHA-256" in guide
    assert "missing" in guide.lower() and "stale" in guide.lower()
    assert all(
        field in guide
        for field in (
            "validated_at",
            "learnlab_revision",
            "guest_capabilities",
            "note",
        )
    )


def test_guide_distinguishes_all_three_validation_levels() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    live_section = guide[
        guide.index("### 8.5 Live acceptance") : guide.index("### 8.6")
    ]

    assert "Offline validation" in guide
    assert "Read-only provider validation" in guide
    assert "Live acceptance" in guide
    assert "explicit approval" in live_section.lower()
    assert "scratch profile" in live_section.lower()
    assert "uncertain" in live_section.lower()
    for number in range(1, 9):
        assert re.search(rf"^{number}\. ", live_section, flags=re.MULTILINE)


def test_nested_virtualization_walkthrough_is_explicitly_uncertified() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    walkthrough = guide[guide.index("## 4. Walkthrough") : guide.index("## 5.")]

    assert "illustrative" in walkthrough.lower()
    assert "uncertified" in walkthrough.lower()
    assert "--include-drafts" in walkthrough


def test_every_documented_start_for_unproven_courses_opts_into_drafts() -> None:
    commands = _start_commands(GUIDE.read_text(encoding="utf-8"))
    commands += _start_commands(README.read_text(encoding="utf-8"))

    assert commands
    assert all("--include-drafts" in command for command in commands), commands


def test_documented_draft_flag_is_exposed_by_real_start_cli() -> None:
    result = CliRunner().invoke(app, ["start", "--help"])

    assert result.exit_code == 0
    assert "--include-drafts" in result.stdout
