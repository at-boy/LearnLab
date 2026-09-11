from pathlib import Path

import pytest

from learnlab.course_certification import CourseMaturity
from learnlab.course_validation import validate_catalog
from learnlab.curriculum import CurriculumCatalog, EnvironmentScope, VerificationType

ROOT = Path(__file__).parents[1] / "src/learnlab/collections"
COURSE_PATH = "proxmox/nixos-template"


def load_course():
    return CurriculumCatalog(ROOT).load_course(COURSE_PATH)


def lesson_text(lesson_id):
    lesson = next(item for item in load_course().lessons if item.id == lesson_id)
    return "\n".join(step.instructions for step in lesson.steps)


def test_bootstrap_has_no_managed_environment():
    course = load_course()
    assert course.maturity is CourseMaturity.DRAFT
    assert course.lessons[0].id == "prerequisites-and-safety"
    for lesson in course.lessons:
        policy = course.effective_environment(lesson)
        assert policy.scope is EnvironmentScope.NONE
        assert policy.provider_capability is None
        assert policy.guest_capabilities == ()
        for step in lesson.steps:
            assert step.verifications
            assert all(
                v.type
                in {
                    VerificationType.TEXT_EVIDENCE,
                    VerificationType.MANUAL_CONFIRMATION,
                }
                for v in step.verifications
            )


def test_bootstrap_validates_without_findings():
    report = validate_catalog(CurriculumCatalog(ROOT), COURSE_PATH)
    assert report.ok
    assert report.findings == ()


def test_installer_teaches_target_specific_steps():
    text = lesson_text("install-nixos")
    for concept in [
        "nixos-generate-config",
        "nixos-install",
        "hardware-configuration.nix",
        "system.stateVersion",
    ]:
        assert concept.lower() in text.lower()
    assert "Installer console" in text
    assert "disk" in text.lower() and "confirm" in text.lower()


def test_access_covers_required_guest_configuration():
    text = lesson_text("configure-lab-access")
    for concept in [
        "services.qemuGuest.enable",
        "services.openssh.enable",
        "environment.systemPackages",
        "nixos-rebuild test",
    ]:
        assert concept in text
    assert "private key" in text.lower()
    assert "public key" in text.lower()


def test_installer_vm_teaches_media_and_boot_boundary():
    text = lesson_text("create-installer-vm")
    for concept in [
        "HTTPS",
        "SHA-256",
        "26.05",
        "x86_64",
        "Q35",
        "OVMF",
        "Secure Boot",
        "DHCP",
    ]:
        assert concept in text


@pytest.mark.parametrize(
    ("lesson_id", "check_id", "accepted", "rejected"),
    [
        ("create-installer-vm", "media-integrity", "checksum", "skip checksum"),
        ("install-nixos", "install-state-version", "26.05", "latest"),
        ("configure-lab-access", "key-material", "public key", "private key"),
    ],
)
def test_added_knowledge_checks_execute_exact_answer_contract(
    lesson_id,
    check_id,
    accepted,
    rejected,
):
    from learnlab.validation import TextEvidenceValidator, ValidationContext

    class AnswerPrompt:
        def __init__(self, answer):
            self.answer = answer

        def ask_text(self, prompt):
            return self.answer

    lesson = next(item for item in load_course().lessons if item.id == lesson_id)
    checks = {
        check.id: check
        for step in lesson.steps
        for check in step.verifications
        if check.type is VerificationType.TEXT_EVIDENCE
    }
    assert set(checks) == {check_id}
    check = checks[check_id]
    for answer, expected in [
        (accepted, True),
        (rejected, False),
        ("", False),
        ("unrelated", False),
    ]:
        result = TextEvidenceValidator().validate(
            ValidationContext(prompt=AnswerPrompt(answer)),
            check,
        )
        assert result.passed is expected
